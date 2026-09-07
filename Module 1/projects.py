from flask import Blueprint

projects_bp = Blueprint('projects', __name__)


@projects_bp.route('/projects')
def projects():
    return "Projects page coming soon"