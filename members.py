import csv
import io

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from db import db
from models import Member
from auth import require_role
from audit import log_action

bp = Blueprint('members', __name__)

PER_PAGE = 25


@bp.route('/members')
@login_required
def members():
    page = request.args.get('page', 1, type=int)
    pagination = (Member.query.filter_by(org_id=current_user.org_id)
                  .order_by(Member.name)
                  .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return render_template('members.html', pagination=pagination, members=pagination.items)


@bp.route('/members/export.csv')
@login_required
def export_members_csv():
    rows = Member.query.filter_by(org_id=current_user.org_id).order_by(Member.name).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['id', 'name', 'phone', 'email', 'debt'])
        yield buf.getvalue()
        for m in rows:
            buf.seek(0)
            buf.truncate(0)
            writer.writerow([m.id, m.name, m.phone, m.email, f'{m.debt:.2f}'])
            yield buf.getvalue()

    return Response(generate(), mimetype='text/csv',
                     headers={'Content-Disposition': 'attachment; filename=members.csv'})


@bp.route('/members/add', methods=['POST'])
@login_required
def add_member():
    name = request.form['name'].strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    db.session.add(Member(org_id=current_user.org_id, name=name, phone=phone, email=email or None))
    log_action('member.create', f'Added "{name}"')
    db.session.commit()
    flash('Member added.')
    return redirect(url_for('members.members'))


@bp.route('/members/<int:member_id>/delete', methods=['POST'])
@login_required
@require_role('admin')
def delete_member(member_id):
    member = Member.query.filter_by(id=member_id, org_id=current_user.org_id).first_or_404()
    try:
        db.session.delete(member)
        log_action('member.delete', f'Deleted "{member.name}"')
        db.session.commit()
        flash('Member deleted.')
    except IntegrityError:
        db.session.rollback()
        flash('Cannot delete this member — they have existing issue/return history.')
    return redirect(url_for('members.members'))
