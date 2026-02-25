import boto3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import uuid
from boto3.dynamodb.conditions import Attr

app = Flask(__name__)
app.secret_key = "secret123"

# AWS REGION (must match DynamoDB region)
aws_region = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=aws_region)
users_table = dynamodb.Table("users")
requests_table = dynamodb.Table("requests")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]

        if "Item" in users_table.get_item(Key={"email": email}):
            flash("Email already exists")
            return redirect(url_for("login"))

        users_table.put_item(Item={
            "email": email,
            "fullname": request.form["fullname"],
            "password": request.form["password"],
            "blood_type": request.form["blood_type"]
        })

        flash("Registration successful")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        res = users_table.get_item(Key={"email": email})
        user = res.get("Item")

        if user and user["password"] == password:
            session["user"] = user
            return redirect(url_for("dashboard"))

        flash("Invalid login")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    response = requests_table.scan(
        FilterExpression=Attr("blood_type").eq(user["blood_type"]) &
                         Attr("status").eq("pending")
    )

    return render_template("dashboard.html",
                           user=user,
                           requests=response.get("Items", []))

@app.route("/request", methods=["GET", "POST"])
def req():
    user = session.get("user")
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        requests_table.put_item(Item={
            "request_id": str(uuid.uuid4()),
            "requester_email": user["email"],
            "blood_type": request.form["blood_type"],
            "location": request.form["location"],
            "urgency": request.form["urgency"],
            "status": "pending",
            "date": datetime.utcnow().isoformat()
        })

        flash("Blood request submitted")
        return redirect(url_for("dashboard"))

    return render_template("request.html")

@app.route("/respond/<request_id>")
def respond(request_id):
    res = requests_table.get_item(Key={"request_id": request_id})
    request_data = res.get("Item")

    if not request_data:
        return redirect(url_for("dashboard"))

    requester = users_table.get_item(
        Key={"email": request_data["requester_email"]}
    ).get("Item")

    return render_template("respond.html",
                           request_data=request_data,
                           requester_data=requester)

@app.route("/donate-blood/<request_id>", methods=["POST"])
def donate_blood(request_id):
    requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #s = :d",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":d": "donated"}
    )
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)