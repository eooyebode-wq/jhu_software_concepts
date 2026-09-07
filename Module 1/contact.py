from flask import Blueprint

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/contact')
def contact():
    return "Contact page coming soon"