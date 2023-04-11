import google.oauth2.id_token
from google.cloud import datastore
from flask import Flask, render_template, request, redirect, flash, make_response
from google.auth.transport import requests
import datetime, calendar, time
from collections import Counter

app = Flask(__name__, static_url_path="/templates")

app.config["SECRET_KEY"] = "somesecretisagoodideatohaveprivacy"
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False

datastore_client = datastore.Client()
firebase_request_adapter = requests.Request()

week_days_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
hours = [
    "00:00",
    "00:30",
    "01:00",
    "01:30",
    "02:00",
    "02:30",
    "03:00",
    "03:30",
    "04:00",
    "04:30",
    "05:00",
    "05:30",
    "06:00",
    "06:30",
    "07:00",
    "07:30",
    "08:00",
    "08:30",
    "09:00",
    "09:30",
    "10:00",
    "10:30",
    "11:00",
    "11:30",
    "12:00",
    "12:30",
    "13:00",
    "13:30",
    "14:00",
    "14:30",
    "15:00",
    "15:30",
    "16:00",
    "16:30",
    "17:00",
    "17:30",
    "18:00",
    "18:30",
    "19:00",
    "19:30",
    "20:00",
    "20:30",
    "21:00",
    "21:30",
    "22:00",
    "22:30",
    "23:00",
    "23:30",
]

user_att = [
    "name",
    "shared_me",
]
cal_att = [
    # key = name+owner
    "name",
    "owner",
    "shared",
]
event_att = [
    # key = name+cal+creator
    "name",
    "creator",
    "start_date",
    "end_date",
    "notes",
    "cal",
    "user",
]

att_list = {"user": user_att, "cal": cal_att, "event": event_att}


def flash_redirect(message, path):
    flash(message)
    return redirect(path)


def create_row_from_data(kind, name, data):
    key = datastore_client.key(kind, name)
    entity = datastore.Entity(key)
    entity.update(data)
    datastore_client.put(entity)


def retrieve_row(kind, name):
    key = datastore_client.key(kind, name)
    result = datastore_client.get(key)
    if result == None:
        return None

    return result.copy()


def create_cal_for_user(user, calname, shared_list):
    if retrieve_row("cal", user + calname) != None:
        print("error! calendar exists!")
        return False
    create_row_from_data(
        "cal", user + calname, {"name": calname, "owner": user, "shared": {}}
    )


def add_user_if_not_added(claims):
    if retrieve_row("user", claims) != None:
        return
    create_row_from_data("user", claims, {"name": claims, "shared_me": ""})
    if create_cal_for_user(claims, "personal calendar", "") != True:
        print("error ! cannot create personal calendar")
    return


def get_session_info():
    id_token = request.cookies.get("token")
    claims = None
    err_msg = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as exc:
            err_msg = str(exc)
            return flash_redirect(err_msg, "/error")
        add_user_if_not_added(claims["email"].split("@")[0])
        return claims["email"].split("@")[0]
    return None


def get_week(day):
    week_days = []
    dominant_month = []
    start = day - datetime.timedelta(days=day.weekday())
    end = start + datetime.timedelta(days=6)

    for wday in range(7):
        d = start + datetime.timedelta(days=wday)
        dominant_month.append(d.month)
        week_days.append(
            {
                "day": d.day,
                "month": d.month,
                "year": d.year,
                "weekday": week_days_name[d.weekday()],
            }
        )

    dominant_month = Counter(dominant_month).most_common(1)[0][0]
    # print(week_days, dominant_month)
    return (week_days, calendar.month_name[dominant_month])


def get_my_cals(user):
    result = query_result("owner", "=", user, "cal")

    result, selected = add_selected_field(result)

    return result, selected


def add_selected_field(result):
    selected = {}
    for k in request.args:
        if k.startswith("selected-"):
            selected[request.args.get(k)] = True

    if selected == {} and request.args.get("cal_list_get") == None:
        list_of_selected = request.cookies.get("selected_cals")
        # print(list_of_selected)
        if list_of_selected != None:
            for i in list_of_selected.split(","):
                selected[i] = True

    # print(selected)
    for r in result:
        if selected.get(r["name"]) != None:
            r["selected"] = "true"
    return result, selected


def query_result(key, comp, val, kind):
    if key == "" or comp == "" or kind == "":
        return [None]
    query = datastore_client.query(kind=kind)
    query.add_filter(key, comp, val)
    fetched = query.fetch()
    if fetched == None or fetched == []:
        return [None]

    print(fetched.num_results)
    result = list(fetched)

    if result == []:
        return [None]
    result_list = []
    for item in result:
        result_list.append(item.copy())

    return result_list


def get_and_set_cal_week():
    day = request.args.get("day")
    offset = request.args.get("offset")
    if offset == None:
        offset = 0
    today = datetime.date.today()

    if day == None:
        day = request.cookies.get("selected_date")
        if day == None:
            day = today
        else:
            day = datetime.datetime.strptime(day, "%d-%m-%Y").date()
    else:
        if day == "today":
            day = today
        else:
            day = datetime.datetime.strptime(day, "%d-%m-%Y").date()

    new_date = day + datetime.timedelta(days=int(offset))
    week_info, dominant_month = get_week(new_date)

    return week_info, new_date.strftime("%d-%m-%Y"), today, dominant_month


def projection_on(kind, prop):
    query = datastore_client.query(kind=kind)
    query.projection = [prop]
    prop_list = []

    for p in query.fetch():
        prop_list.append(p[prop])

    return prop_list


def add_calendar(claims):
    calname = request.args.get("calname")
    # print(calname)
    if calname == None:
        return False

    if calname == "":
        flash("Please Enter Calendar Name")
        return False

    if retrieve_row("cal", calname + claims) != None:
        flash("Calendar Already Exist")
        return False

    shared_dic = {}
    for r in request.args:
        if r == "calname":
            continue
        shared_dic[request.args[r]] = request.args[r]

    create_row_from_data(
        "cal",
        calname + claims,
        {"name": calname, "owner": claims, "shared": shared_dic},
    )
    flash(
        "Calendar Added Successfully.",
    )


def add_event(claims):
    event_name = request.args.get("event_name")
    start_date = request.args.get("start_date")
    start_time = request.args.get("start_time")
    end_date = request.args.get("end_date")
    end_time = request.args.get("end_time")
    calname = request.args.get("cal_name")
    notes = request.args.get("notes")

    if event_name == None:
        return False

    if len(event_name) > 15:
        flash("Evenet name should be less than 15 character!")
        return False

    if (
        event_name == ""
        or start_date == ""
        or end_date == ""
        or calname == ""
        or start_time == ""
        or end_time == ""
    ):
        flash("Please Fill neccessary Fields!")
        return False

    if retrieve_row("event", event_name + calname + claims) != None:
        flash("Event Exists! Choose different name!")
        return False

    start_date = datetime.datetime.strptime(
        start_date + " " + start_time, "%Y-%m-%d %H:%M"
    ).timetuple()
    end_date = datetime.datetime.strptime(
        end_date + " " + end_time, "%Y-%m-%d %H:%M"
    ).timetuple()

    if start_date > end_date:
        flash("Start Date is later than End Date!")
        return False

    will_share = []

    for r in request.args:
        if r.startswith("user"):
            will_share.append(request.args.get(r))

    if len(will_share) == 0:
        create_row_from_data(
            "event",
            event_name + calname + claims,
            {
                "name": event_name,
                "creator": claims,
                "start_date": time.mktime(start_date),
                "end_date": time.mktime(end_date),
                "notes": notes,
                "cal": calname,
                "user": claims,
            },
        )
        flash("Event Added Successfully.")

    if len(will_share) > 0:
        return




def fill_mat(my_cals, week_info, selected_cals):
    color_list = ["bg-warning", "bg-info", "bg-danger", "big-primary", "bg-success", "bg-warning", "bg-info", "bg-success", "bg-danger", "big-primary"]
    event_mat = {}
    for hour in hours:
        event_mat[hour] = {}
        for wd in week_days_name:
            event_mat[hour][wd] = {}
            event_mat[hour][wd]["color"] = "None"
            event_mat[hour][wd]["event_list"] = []

    print(selected_cals)
    print(week_info)

    query = datastore_client.query(kind="event")

    if selected_cals == []:
        return
    query.add_filter("cal", "IN", selected_cals)
    result = list(query.fetch())
    print(result)
    print()
    week_start = (
        str(week_info[0]["year"])
        + "-"
        + str(week_info[0]["month"])
        + "-"
        + str(week_info[0]["day"])
        + " "
        + "00:00"
    )
    week_end = (
        str(week_info[6]["year"])
        + "-"
        + str(week_info[6]["month"])
        + "-"
        + str(week_info[6]["day"])
        + " "
        + "23:30"
    )
    week_start = datetime.datetime.strptime(week_start, "%Y-%m-%d %H:%M")
    week_end = datetime.datetime.strptime(week_end, "%Y-%m-%d %H:%M")


    for event in result:
        start_t = datetime.datetime.fromtimestamp(event["start_date"])
        end_t = datetime.datetime.fromtimestamp(event["end_date"])
        event["start_date"] = start_t.strftime("%Y-%m-%d")
        event["end_date"] = end_t.strftime("%Y-%m-%d")
        event["start_time"] =  start_t.strftime("%H:%M")
        event["end_time"] =  end_t.strftime("%H:%M")
        visit = "true"
        while start_t <= end_t:
            if start_t >= week_start and start_t <= week_end:
                weekday = week_days_name[start_t.weekday()]
                clock = start_t.strftime("%H:%M")
                event["vis"] = visit
                event_mat[clock][weekday]["event_list"].append(event.copy())
                event_mat[clock][weekday]["color"] = color_list[len(event_mat[clock][weekday]["event_list"])-1]
            visit = "false"
            start_t += datetime.timedelta(minutes=30)

    #print(event_mat)
    return event_mat

def delete_event(claims):
    if request.args.get("delete_event") == None:
        return
    
    if request.args.get("user") != claims:
        flash("You are not the creator of event but you can Unsubscribe!")
        return
    delete_row("event", request.args.get("event")+request.args.get("cal")+claims)
    flash("Event Deleted Successfully")

def delete_row(kind, name):
	key = datastore_client.key(kind, name)
	datastore_client.delete(key)

@app.route("/error")
def error():
    return render_template("50x.html")


@app.route("/", methods=["GET", "POST"])
def root():
    claims = get_session_info()

    if not claims:
        return render_template(
            "index.html",
            is_logged_in=False,
            pagename="Homepage",
        )

    delete_event(claims)

    user_list = projection_on("user", "name")
    # print(user_list)

    add_calendar(claims)
    add_event(claims)
    my_cals, selected_cals = get_my_cals(claims)

    week_info, selected_date, today, dominant_month = get_and_set_cal_week()

    # print("week info: ", week_info)
    # print("my_cals: ", my_cals)

    event_mat = fill_mat(my_cals, week_info, list(selected_cals.keys()))

  

    temp = render_template(
        "index.html",
        today=today,
        wi=week_info,
        dominant_month=dominant_month,
        claims=claims,
        is_logged_in=True,
        pagename="Homepage",
        my_cals=my_cals,
        user_list=user_list,
        hours=hours,
        event_mat=event_mat,
    )

    resp = make_response(temp)
    resp.set_cookie("selected_date", selected_date)
    resp.set_cookie("selected_cals", ",".join(list(selected_cals.keys())))

    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)


"""
 
 driver_att = [
		"name",
		"age",
		"pole-position",
		"wins",
		"points",
		"titles",
		"fastest-laps",
		"team",
		]
team_att = [
		"name",
		"year-found",
		"pole-position",
		"wins",
		"titles",
		"finished-position",
		]
att_list = {"driver": driver_att, "team": team_att}

def flash_redirect(message, path):
	flash(message)
	return redirect(path)


def get_session_info():
	id_token = request.cookies.get("token")
	claims = None
	err_msg = None
	if id_token:
		try:
			claims = google.oauth2.id_token.verify_firebase_token(
					id_token, firebase_request_adapter, clock_skew_in_seconds=20
					)
		except ValueError as exc:
			err_msg = str(exc)
			return flash_redirect(err_msg, "/error")
		return claims
	return None


def retrieve_row(kind, name):
	key = datastore_client.key(kind, name)
	result = datastore_client.get(key)
	if result == None:
		return None
	return result.copy()


def update_row(kind, name):
	with datastore_client.transaction():
		key = datastore_client.key(kind, name)
		entity = datastore_client.get(key)
		for i in range(1, len(att_list[kind]), 1):
			entity[att_list[kind][i]] = request.form[att_list[kind][i]]
		datastore_client.put(entity)


def create_row(kind, name):
	key = datastore_client.key(kind, name)
	entity = datastore.Entity(key)
	obj = dict()
	for elem in att_list[kind]:
		obj[elem] = request.form[elem]
	entity.update(obj)
	datastore_client.put(entity)


def delete_row(kind, name):
	key = datastore_client.key(kind, name)
	datastore_client.delete(key)


def query_result(key, comp, val, kind):
	if key == '' or comp == '' or kind == '':
		return [None]
	query = datastore_client.query(kind=kind)
	query.add_filter(key, comp, val)
	result = list(query.fetch())
	if result == []:
		return [None]
	result_list = []
	for item in result:
		result_list.append(item.copy())

	return result_list


def priority_taging(retreived, kind):
	for elem in att_list[kind]:
		tag1, tag2 = tag_returner(retreived[0][elem], retreived[1][elem], elem)
		retreived[0][elem], retreived[1][elem] = (retreived[0][elem], tag1), (
				retreived[1][elem],
				tag2,
				)
	return retreived


def tag_returner(a, b, col):
	if a == "":
		a = "0"
	if b == "":
		b = "0"

	lower_better = ["age", "finished-position", "year-found"]
	if col == "team" or col == "name":
		return "", ""
	if col in lower_better:
		if int(a, 36) > int(b, 36):
			return "down", "up"
		elif a == b:
			return "tie", "tie"
		else:
			return "up", "down"

	if int(a, 36) > int(b, 36):
		return "up", "down"
	elif a == b:
		return "tie", "tie"
	else:
		return "down", "up"

def projection_on(kind, prop):
	query = datastore_client.query(kind=kind)
	query.projection = [prop]
	prop_list = []

	for p in query.fetch():
		prop_list.append(p[prop])

	return prop_list

@app.route("/add/<kind>", methods=["POST", "GET"])
def add(kind):
	claims = get_session_info()
	if claims:
		if request.method == "POST":
			if request.form['name'] == '':
				return flash_redirect("Name Field Can Not Be Empty!", "/add/" + kind)
			if retrieve_row(kind, request.form["name"]) != None:
				return flash_redirect("Already Exist!", "/add/" + kind)

			create_row(kind, request.form["name"])
			return flash_redirect("Added Successfully.", "/add/" + kind)

		return render_template(
				"add.html", claims=claims, data=att_list, kind=kind, pagename="Add " + kind
				)
	return flash_redirect("Please Login First", "/")


@app.route("/query", methods=["POST", "GET"])
def query():
	claims = get_session_info()

	if request.method == "GET":
		return render_template(
				"query.html", claims=claims, data=att_list, pagename="Query Page"
				)

	query_key = request.form["query_key"].split(".")
	result = query_result(query_key[1], ">=", request.form["query_value"], query_key[0])
	if result[0] == None:
		return flash_redirect("No data available for the Query", "/query")

	return render_template(
			"query.html",
			claims=claims,
			result=result,
			data=att_list,
			kind=query_key[0],
			pagename="Query Page",
			)


@app.route("/compare", methods=["POST", "GET"])
def compare():
	claims = get_session_info()
	kind = None
	result = None
	dd_data = {}
	pagename = "Compare Page"

	dd_data["team"] = projection_on("team", "name")
	dd_data["driver"] = projection_on("driver", "name")

	if request.method == "GET":
		return render_template(
				"compare.html", claims=claims, data=att_list, pagename=pagename, dd_data=dd_data
				)

	retreived = []
	retreived.append(
			query_result("name", "=", request.form["name1"], request.form["compare-kind"])[
				0
				]
			)
	retreived.append(
			query_result("name", "=", request.form["name2"], request.form["compare-kind"])[
				0
				]
			)

	if (
			retreived[0] == None
			or retreived[1] == None
			or retreived[0]["name"] == retreived[1]["name"]
			):
		return flash_redirect("Oooops! Try add some entities and then you'll see them in the dropdown, OR maybe comparing same entity? Don't do!", "/compare")

	retreived = priority_taging(retreived, request.form["compare-kind"])
	return render_template(
			"compare.html",
			claims=claims,
			data=att_list,
			retreived=retreived,
			kind=request.form["compare-kind"],
			pagename=pagename,
			dd_data=dd_data
			)


@app.route("/update/<kind>/<name>", methods=["POST", "GET"])
def update(kind, name):
	claims = get_session_info()

	if not claims:
		return flash_redirect("Please Login First", "/query")

	if request.method == "POST":
		update_row(kind, name)
		return flash_redirect("Updated Successfully", "/query")

	result = retrieve_row(kind, name)
	return render_template(
			"update.html",
			claims=claims,
			result=result,
			data=att_list,
			kind=kind,
			pagename="Update Page",
			)


@app.route("/delete/<kind>/<name>")
def delete(kind, name):
	claims = get_session_info()

	if not claims:
		return flash_redirect("Please Login First", "/query")

	delete_row(kind, name)
	return flash_redirect("Deleted Successfully", "/query")


@app.route("/error")
def error():
	return render_template("50x.html")


@app.route("/")
def root():
	claims = get_session_info()
	return render_template("index.html", claims=claims, pagename="Homepage")


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=8080, debug=True)
 """
