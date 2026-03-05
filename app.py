import boto3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import uuid
from boto3.dynamodb.conditions import Attr

app = Flask(__name__)
app.secret_key = "your_secret_key"

# DynamoDB setup
aws_region = "us-east-1"
dynamodb = boto3.resource("dynamodb", region_name=aws_region)

users_table = dynamodb.Table("users")
requests_table = dynamodb.Table("requests")


# ---------------- HOME ----------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        fullname = request.form.get("fullname")
        email = request.form.get("email")
        password = request.form.get("password")
        blood_type = request.form.get("blood_type")

        response = users_table.get_item(Key={"email": email})

        if "Item" in response:
            flash("Email already exists! Please login.")
            return redirect(url_for("login"))

        users_table.put_item(
            Item={
                "email": email,
                "fullname": fullname,
                "password": password,
                "blood_type": blood_type,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        session["user"] = {
            "fullname": fullname,
            "email": email,
            "blood_type": blood_type
        }

        flash("Registration successful!")
        return redirect(url_for("confirm"))

    return render_template("register.html")


# ---------------- CONFIRMATION ----------------

@app.route("/confirm")
def confirm():
    user = session.get("user")
    return render_template("confirmation.html", user=user)


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        response = users_table.get_item(Key={"email": email})
        user = response.get("Item")

        if user and user["password"] == password:

            session["user"] = {
                "fullname": user["fullname"],
                "email": user["email"],
                "blood_type": user["blood_type"]
            }

            return redirect(url_for("dashboard"))

        flash("Invalid login credentials")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    response = requests_table.scan(
        FilterExpression=Attr("blood_type").eq(user["blood_type"]) &
                         Attr("status").eq("pending")
    )

    requests = response.get("Items", [])

    return render_template("dashboard.html",
                           user=user,
                           requests=requests)


# ---------------- CREATE REQUEST ----------------

@app.route("/request", methods=["GET", "POST"])
def req():

    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":

        request_id = str(uuid.uuid4())

        location = request.form.get("location")
        blood_type = request.form.get("blood_type")
        urgency = request.form.get("urgency")

        requests_table.put_item(
            Item={
                "request_id": request_id,
                "requester_email": user["email"],
                "blood_type": blood_type,
                "location": location,
                "urgency": urgency,
                "status": "pending",
                "date": datetime.utcnow().isoformat()
            }
        )

        flash("Blood request submitted!")

        return redirect(url_for("dashboard"))

    return render_template("request.html", user=user)


# ---------------- RESPOND TO REQUEST ----------------

@app.route("/respond/<request_id>")
def respond(request_id):

    user = session.get("user")

    response = requests_table.get_item(Key={"request_id": request_id})
    request_data = response.get("Item")

    if not request_data:
        return redirect(url_for("dashboard"))

    requester_email = request_data["requester_email"]

    requester_response = users_table.get_item(Key={"email": requester_email})
    requester_data = requester_response.get("Item")

    return render_template(
        "respond.html",
        request_data=request_data,
        requester_data=requester_data,
        user=user
    )


# ---------------- DONATE BLOOD ----------------

@app.route("/donate-blood/<request_id>", methods=["POST"])
def donate_blood(request_id):

    requests_table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET #st = :new_status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":new_status": "donated"}
    )

    flash("Donation confirmed!")

    return redirect(url_for("dashboard"))


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
