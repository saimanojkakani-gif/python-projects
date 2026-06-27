import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["ADMIN_USERNAME"] = os.environ.get("ADMIN_USERNAME", "admin")
app.config["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + os.path.join(str(BASE_DIR), "quiz.db"),
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(300), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.String(5), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=True)
    subject = db.relationship("Subject", backref=db.backref("questions", lazy=True))


class QuizResult(db.Model):
    __tablename__ = "quiz_results"

    id = db.Column(db.Integer, primary_key=True)
    participant_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def ensure_schema():
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    if "subjects" not in table_names:
        Subject.__table__.create(bind=db.engine)

    if "questions" not in table_names:
        Question.__table__.create(bind=db.engine)
        return

    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    if "subject_id" not in question_columns:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE questions ADD COLUMN subject_id INTEGER"))

        default_subject = Subject.query.first()
        if default_subject is None:
            default_subject = Subject(name="General Knowledge")
            db.session.add(default_subject)
            db.session.commit()

        Question.query.filter(Question.subject_id.is_(None)).update(
            {Question.subject_id: default_subject.id}, synchronize_session=False
        )
        db.session.commit()


def seed_questions():
    if Question.query.first():
        return

    subject = Subject.query.filter_by(name="General Knowledge").first()
    if subject is None:
        subject = Subject(name="General Knowledge")
        db.session.add(subject)
        db.session.commit()

    questions = [
        Question(
            question_text="What does Flask primarily provide?",
            option_a="A web framework for Python",
            option_b="A database engine",
            option_c="A CSS library",
            option_d="A machine learning tool",
            correct_option="a",
            subject=subject,
        ),
        Question(
            question_text="Which SQL database is commonly used with Flask apps?",
            option_a="MongoDB",
            option_b="PostgreSQL",
            option_c="Redis",
            option_d="Elasticsearch",
            correct_option="b",
            subject=subject,
        ),
        Question(
            question_text="What is a template engine used in Flask?",
            option_a="Jinja2",
            option_b="Django",
            option_c="TensorFlow",
            option_d="Pandas",
            correct_option="a",
            subject=subject,
        ),
    ]
    db.session.add_all(questions)
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_schema()
    seed_questions()


@app.route("/")
def index():
    subjects = Subject.query.order_by(Subject.name).all()
    return render_template("index.html", subjects=subjects)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == app.config["ADMIN_USERNAME"] and password == app.config["ADMIN_PASSWORD"]:
            session["admin_logged_in"] = True
            flash("Logged in successfully.", "success")
            return redirect(url_for("admin"))

        flash("Invalid username or password.", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "subject":
            subject_name = request.form.get("subject_name", "").strip()
            if not subject_name:
                flash("Please enter a subject name.", "danger")
            elif Subject.query.filter_by(name=subject_name).first():
                flash("That subject already exists.", "warning")
            else:
                db.session.add(Subject(name=subject_name))
                db.session.commit()
                flash("Subject added successfully.", "success")

        elif form_type == "question":
            subject_id = request.form.get("question_subject_id", type=int)
            question_text = request.form.get("question_text", "").strip()
            option_a = request.form.get("option_a", "").strip()
            option_b = request.form.get("option_b", "").strip()
            option_c = request.form.get("option_c", "").strip()
            option_d = request.form.get("option_d", "").strip()
            correct_option = request.form.get("correct_option", "").strip().lower()

            if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
                flash("Please complete all question fields.", "danger")
            elif subject_id is None:
                flash("Please choose a subject.", "danger")
            else:
                subject = Subject.query.get(subject_id)
                if subject is None:
                    flash("Selected subject does not exist.", "danger")
                else:
                    db.session.add(
                        Question(
                            question_text=question_text,
                            option_a=option_a,
                            option_b=option_b,
                            option_c=option_c,
                            option_d=option_d,
                            correct_option=correct_option,
                            subject=subject,
                        )
                    )
                    db.session.commit()
                    flash("Question added successfully.", "success")

        return redirect(url_for("admin"))

    subjects = Subject.query.order_by(Subject.name).all()
    questions = Question.query.order_by(Question.id.desc()).all()
    return render_template("admin.html", subjects=subjects, questions=questions)


@app.route("/subjects/<int:subject_id>", methods=["GET", "POST"])
def subject_page(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    if request.method == "POST":
        question_text = request.form.get("question_text", "").strip()
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()
        correct_option = request.form.get("correct_option", "").strip().lower()

        if not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
            flash("Please complete all question fields.", "danger")
        else:
            db.session.add(
                Question(
                    question_text=question_text,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_option=correct_option,
                    subject=subject,
                )
            )
            db.session.commit()
            flash("Question added successfully.", "success")
            return redirect(url_for("subject_page", subject_id=subject.id))

    questions = Question.query.filter_by(subject_id=subject.id).order_by(Question.id.desc()).all()
    return render_template("subject_page.html", subject=subject, questions=questions)


@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if request.method == "POST":
        participant_name = request.form.get("participant_name", "Guest").strip() or "Guest"
        questions = Question.query.order_by(Question.id).all()
        score = 0

        for question in questions:
            selected = request.form.get(f"q{question.id}", "")
            if selected == question.correct_option:
                score += 1

        result = QuizResult(
            participant_name=participant_name,
            score=score,
            total_questions=len(questions),
        )
        db.session.add(result)
        db.session.commit()
        flash("Quiz submitted successfully.", "success")
        return redirect(url_for("results", result_id=result.id))

    questions = Question.query.order_by(Question.id).all()
    return render_template("quiz.html", questions=questions)


@app.route("/results/<int:result_id>")
def results(result_id):
    result = QuizResult.query.get_or_404(result_id)
    return render_template("results.html", result=result)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
