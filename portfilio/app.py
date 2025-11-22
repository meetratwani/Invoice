from flask import Flask, render_template

app = Flask(__name__)

# Replace these with your real projects
projects = [
    {
        "name": "Invoice Generator – Smart, Simple & Powerful",
        "description": (
            "The Invoice Generator is a fast and intuitive tool designed to simplify your billing process. "
            "Whether you're a freelancer, small business owner, or managing a growing company, this app helps "
            "you create clean, professional invoices in seconds. With built-in features like credit management, "
            "auto-calculations, tax handling, and easy customer tracking, it ensures your workflow stays smooth "
            "and organized. Generate, download, and share invoices effortlessly—anytime, anywhere."
        ),
        "tech": ["Python", "Flask", "SQLite", "HTML", "CSS", "JavaScript"],
        "github": "https://github.com/meetratwani",  # update with specific repo if available
        "demo": "https://rsanjustore.onrender.com/?phone=&date=",
    },
    {
        "name": "Aimers Saarthi",
        "description": (
            "Aimers Saarthi is a smart guidance platform designed to support students and learners at every step of "
            "their journey. Whether you're choosing a career path, preparing for exams, or looking for the right "
            "mentorship, Aimers Saarthi helps you gain clarity with structured roadmaps, personalized guidance, and "
            "actionable strategies. With a focus on practical direction over confusion, it aims to be your reliable "
            "companion for making confident, informed decisions about your future."
        ),
        "tech": ["Python", "Flask", "HTML", "CSS", "JavaScript"],
        "github": "https://github.com/meetratwani",  # update with specific repo if available
        "demo": "https://aimers-cx0o.onrender.com/signup",
    },
    {
        "name": "Portfolio Website",
        "description": "Animated personal portfolio built with Flask, HTML, CSS, and JS.",
        "tech": ["Flask", "HTML", "CSS", "JavaScript"],
        "github": "https://github.com/meetratwani",  # put specific repo link
        "demo": "#",
    },
]


@app.route("/")
def home():
    return render_template("index.html", projects=projects)


if __name__ == "__main__":
    app.run(debug=True)
