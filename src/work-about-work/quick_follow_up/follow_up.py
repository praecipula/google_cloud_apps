from flask import Blueprint,render_template,request

follow_up = Blueprint('follow_up', __name__, template_folder='templates')

@follow_up.route("/", methods=['GET'])
def show():
    return render_template("get_follow_up.html")

@follow_up.route("/", methods=['POST'])
def create():
    task_id = request.form["task_url"]
    return render_template("post_follow_up.html", source_task_url = request.form['task_url'])
