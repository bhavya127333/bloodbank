import boto3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import uuid
from boto3.dynamodb.conditions import Attr

app = Flask(__name__)
app.secret_key = "bloodbridge_secret"

# ---------------- DynamoDB Setup ----------------

aws_region = "ap-south-1"

dynamodb = boto3.resource(
    "dynamodb",
    region_name=aws_region
)

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

        if not fullname or not email or not password or not blood_type:
            flash("All fields are required")
            return redirect(url_for("register"))

        response = users_table.get_item(Key={"email": email})

        if "Item" in response:
            flash("Email already exists. Please login.")
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

        flash("Registration successful")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        # Prevent DynamoDB empty key error
        if not email or not password:
            flash("Email and Password are required")
            return redirect(url_for("login"))

        try:
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

        except Exception as e:
            print("Login error:", e)
            flash("Login error occurred")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    try:

        response = requests_table.scan(
            FilterExpression=Attr("blood_type").eq(user["blood_type"]) &
                             Attr("status").eq("pending")
        )

        requests = response.get("Items", [])

    except Exception as e:
        print("Dashboard error:", e)
        requests = []

    return render_template("dashboard.html", user=user, requests=requests)


# ---------------- CREATE REQUEST ----------------

@app.route("/request", methods=["GET", "POST"])
def req():

    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":

        location = request.form.get("location")
        blood_type = request.form.get("blood_type")
        urgency = request.form.get("urgency")

        if not location or not blood_type or not urgency:
            flash("Please fill all fields")
            return redirect(url_for("req"))

        request_id = str(uuid.uuid4())

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

        flash("Blood request submitted successfully!")

        return redirect(url_for("dashboard"))

    return render_template("request.html", user=user)


# ---------------- RESPOND ----------------

@app.route("/respond/<request_id>")
def respond(request_id):

    user = session.get("user")

    if not user:
        return redirect(url_for("login"))

    response = requests_table.get_item(Key={"request_id": request_id})
    request_data = response.get("Item")

    if not request_data:
        flash("Request not found")
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

    try:

        requests_table.update_item(
            Key={"request_id": request_id},
            UpdateExpression="SET #s = :status",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":status": "donated"}
        )

        flash("Donation confirmed!")

    except Exception as e:
        print("Donation error:", e)

    return redirect(url_for("dashboard"))


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()
    flash("Logged out successfully")

    return redirect(url_for("login"))


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
