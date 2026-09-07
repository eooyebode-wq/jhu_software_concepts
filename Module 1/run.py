from flask import Flask
from home import home_bp
from contact import contact_bp
from projects import projects_bp


app = Flask(__name__)
app.register_blueprint(home_bp)
app.register_blueprint(contact_bp)
app.register_blueprint(projects_bp)





if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
