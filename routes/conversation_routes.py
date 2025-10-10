from flask import Blueprint, render_template, request, jsonify, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from models import db, User, Conversation, Message, ActivityLog
from datetime import datetime
import re

conversations_bp = Blueprint('conversations', __name__)


def _ensure_participant(conv: Conversation) -> None:
    if current_user.role not in ('client', 'company'):
        abort(403)
    if current_user.role == 'client' and conv.client_id != current_user.id:
        abort(403)
    if current_user.role == 'company' and conv.company_id != current_user.id:
        abort(403)


def _detect_external_contact(content: str) -> bool:
    text = (content or '').lower()
    # crude patterns for emails, URLs, and phone numbers/WhatsApp
    email_re = re.compile(r"[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+")
    url_re = re.compile(r"https?://|www\\.")
    phone_re = re.compile(r"(\+?\d[\d\s\-]{7,}\d)")
    whatsapp_re = re.compile(r"whats(app)?|wa\.me|chat\.whatsapp\.com")
    sms_re = re.compile(r"\bsms\b")
    return bool(email_re.search(text) or url_re.search(text) or phone_re.search(text) or whatsapp_re.search(text) or sms_re.search(text))


@conversations_bp.route('/conversations')
@login_required
def list_conversations():
    if current_user.role == 'client':
        convs = (Conversation.query
                 .filter_by(client_id=current_user.id)
                 .order_by(Conversation.created_at.desc())
                 .all())
    elif current_user.role == 'company':
        convs = (Conversation.query
                 .filter_by(company_id=current_user.id)
                 .order_by(Conversation.created_at.desc())
                 .all())
    else:
        abort(403)

    # Eager fetch the other party names
    other_parties = {}
    for c in convs:
        other_user_id = c.company_id if current_user.role == 'client' else c.client_id
        if other_user_id not in other_parties:
            other_parties[other_user_id] = User.query.get(other_user_id)

    return render_template('conversations/list.html', conversations=convs, other_parties=other_parties)


@conversations_bp.route('/conversations/<int:conversation_id>')
@login_required
def conversation_detail(conversation_id: int):
    conv = Conversation.query.get_or_404(conversation_id)
    _ensure_participant(conv)
    other_user = User.query.get(conv.company_id if current_user.role == 'client' else conv.client_id)
    messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.timestamp.asc()).all()
    return render_template('conversations/detail.html', conversation=conv, other_user=other_user, messages=messages)


@conversations_bp.route('/api/conversations/<int:conversation_id>/messages')
@login_required
def api_conversation_messages(conversation_id: int):
    conv = Conversation.query.get_or_404(conversation_id)
    _ensure_participant(conv)

    since_raw = request.args.get('since')
    q = Message.query.filter_by(conversation_id=conv.id)
    if since_raw:
        try:
            since_dt = datetime.fromisoformat(since_raw)
            q = q.filter(Message.timestamp > since_dt)
        except Exception:
            pass
    q = q.order_by(Message.timestamp.asc())
    items = q.all()
    def serialize(m: Message):
        return {
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': (m.sender.name if m.sender else 'مستخدم'),
            'content': m.content,
            'timestamp': m.timestamp.isoformat()
        }
    return jsonify({'messages': [serialize(m) for m in items]})


@conversations_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    payload = request.get_json(silent=True) or request.form
    conversation_id_raw = payload.get('conversation_id')
    content = (payload.get('content') or '').strip()

    # Basic validation
    try:
        conversation_id = int(conversation_id_raw)
    except Exception:
        return jsonify({'error': 'conversation_id is required'}), 400
    if not content:
        return jsonify({'error': 'لا يمكن إرسال رسالة فارغة'}), 400
    if len(content) > 3000:
        return jsonify({'error': 'النص طويل جداً'}), 400
    if _detect_external_contact(content):
        return jsonify({'error': 'مشاركة وسائل تواصل خارجية غير مسموح بها داخل النظام'}), 400

    conv = Conversation.query.get_or_404(conversation_id)
    _ensure_participant(conv)

    if conv.status == 'closed':
        return jsonify({'error': 'المحادثة مغلقة'}), 400

    msg = Message(conversation_id=conv.id, sender_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='message_sent'))
    db.session.commit()

    return jsonify({'ok': True, 'message': {
        'id': msg.id,
        'sender_id': msg.sender_id,
        'sender_name': current_user.name,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat(),
    }})


@conversations_bp.route('/conversations/<int:conversation_id>/status', methods=['POST'])
@login_required
def update_conversation_status(conversation_id: int):
    conv = Conversation.query.get_or_404(conversation_id)
    _ensure_participant(conv)

    if current_user.role != 'company':
        return jsonify({'error': 'فقط الشركة يمكنها تغيير حالة المحادثة'}), 403

    new_status = (request.form.get('status') or (request.get_json(silent=True) or {}).get('status') or '').strip()
    if new_status not in ('open', 'pending', 'closed'):
        return jsonify({'error': 'حالة غير صالحة'}), 400

    conv.status = new_status
    db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='status_changed', meta=new_status))
    db.session.commit()

    return jsonify({'ok': True, 'status': conv.status})


@conversations_bp.route('/conversations/start/<int:company_id>', methods=['POST', 'GET'])
@login_required
def start_conversation(company_id: int):
    # Only clients can initiate
    if current_user.role != 'client':
        abort(403)
    company = User.query.filter_by(id=company_id, role='company').first()
    if not company:
        abort(404)

    conv = Conversation.query.filter_by(client_id=current_user.id, company_id=company.id).first()
    created = False
    if not conv:
        conv = Conversation(client_id=current_user.id, company_id=company.id, status='open')
        db.session.add(conv)
        db.session.flush()
        db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='conversation_created'))
        db.session.commit()
        created = True

    if request.method == 'POST':
        # optionally accept an initial message
        content = (request.form.get('content') or (request.get_json(silent=True) or {}).get('content') or '').strip()
        if content:
            if _detect_external_contact(content):
                return jsonify({'error': 'مشاركة وسائل تواصل خارجية غير مسموح بها داخل النظام'}), 400
            msg = Message(conversation_id=conv.id, sender_id=current_user.id, content=content)
            db.session.add(msg)
            db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='message_sent'))
            db.session.commit()
            return jsonify({'ok': True, 'conversation_id': conv.id})

    # GET: redirect to detail page
    return redirect(url_for('conversations.conversation_detail', conversation_id=conv.id))
