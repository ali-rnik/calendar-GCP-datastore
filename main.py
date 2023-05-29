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


def create_cal_for_user(user, calname):
    if retrieve_row("cal", user + "_._" + calname) != None:
        print("error! calendar exists!")
        return False
    create_row_from_data(
        "cal", calname + "_._" + user, {"name": calname, "owner": user, "shared": {}}
    )
    return True


def add_user_if_not_added(claims):
    if retrieve_row("user", claims) != None:
        return
    create_row_from_data("user", claims, {"name": claims, "shared_me": {}})
    if create_cal_for_user(claims, "personalCalendar") != True:
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
    return (week_days, calendar.month_name[dominant_month])


def get_my_cals(claims):
    result = query_result("owner", "=", claims, "cal")
    shared_cals = get_shared_cals_list(claims)
    if result == [None]:
        result = []

    for item in shared_cals:
        item["shared_me"] = "true"
        result.append(item)

    result, selected = add_selected_field(result)
    return result, selected


def add_selected_field(result):
    if result == [None] or result == None or result == "":
        return [], {}
    selected = {}
    for k in request.args:
        if k.startswith("selected-"):
            selected[request.args.get(k)] = True

    if selected == {} and request.args.get("cal_list_get") == None:
        list_of_selected = request.cookies.get("selected_cals")
        if list_of_selected != None and list_of_selected != "":
            for i in list_of_selected.split(","):
                selected[i] = True

    for r in result:
        if r != None and selected.get(r.get("name") + "_._" + r["owner"]) != None:
            r["selected"] = "true"
    return result, selected


def get_shared_cals_list(claims):
    result = query_result("name", "=", claims, "user")[0]["shared_me"]
    neat_list = []
    for k, v in result.items():
        if v == "yes":
            spl = k.split("_._")
            neat_list.append({"name": spl[0], "owner": spl[1]})
    return neat_list


def query_result(key, comp, val, kind):
    if key == "" or comp == "" or kind == "":
        return [None]
    query = datastore_client.query(kind=kind)
    query.add_filter(key, comp, val)
    fetched = query.fetch()
    if fetched == None or fetched == []:
        return [None]

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


def add_or_edit_calendar(claims):
    calname = request.args.get("calname")
    if calname == None:
        return False

    if calname == "":
        flash("Please Enter Calendar Name")
        return False

    if calname.find(" ") != -1:
        flash("Calendar Name Can not contains whitespace.")
        return False

    shared_dic = {}
    for r in request.args:
        if r == "calname" or r == "edit_calendar":
            continue
        shared_dic[request.args[r]] = request.args[r]

    if retrieve_row("cal", calname + "_._" + claims) != None:
        if request.args.get("edit_calendar") == "edit_calendar":
            create_row_from_data(
                "cal",
                calname + "_._" + claims,
                {"name": calname, "owner": claims, "shared": shared_dic},
            )

            query = datastore_client.query(kind="user")
            result = list(query.fetch())
            for res in result:
                new_shared_me = {}
                for k in res["shared_me"]:
                    if k.endswith(claims):
                        continue
                    new_shared_me[k] = res["shared_me"][k]
                res["shared_me"] = new_shared_me
                create_row_from_data("user", res["name"], res)

            for user in shared_dic:
                result = query_result("name", "=", user, "user")[0]
                result["shared_me"][calname + "_._" + claims] = "no"
                create_row_from_data(
                    "user",
                    user,
                    result,
                )

            flash(
                "Calendar edited Successfully.",
            )
            return
        flash("Calendar Already Exist")
        return False

    create_row_from_data(
        "cal",
        calname + "_._" + claims,
        {"name": calname, "owner": claims, "shared": shared_dic},
    )

    query = datastore_client.query(kind="user")
    result = list(query.fetch())
    for res in result:
        new_shared_me = {}
        for k in res["shared_me"]:
            if k.endswith(claims):
                continue
            new_shared_me[k] = res["shared_me"][k]
        res["shared_me"] = new_shared_me
        create_row_from_data("user", res["name"], res)

    for user in shared_dic:
        result = query_result("name", "=", user, "user")[0]
        result["shared_me"][calname + "_._" + claims] = "no"
        create_row_from_data(
            "user",
            user,
            result,
        )

    flash(
        "Calendar Added Successfully.",
    )


def add_or_edit_event(claims):
    event_name = request.args.get("event_name")
    start_date = request.args.get("start_date")
    start_time = request.args.get("start_time")
    end_date = request.args.get("end_date")
    end_time = request.args.get("end_time")
    calname = request.args.get("cal_name")
    notes = request.args.get("notes")

    if event_name == None:
        return False

    if len(event_name) > 15 or event_name.find(" ") != -1:
        flash(
            "Evenet name should be less than 15 character and should not contains whitespace"
        )
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

    start_date = datetime.datetime.strptime(
        start_date + " " + start_time, "%Y-%m-%d %H:%M"
    ).timetuple()
    end_date = datetime.datetime.strptime(
        end_date + " " + end_time, "%Y-%m-%d %H:%M"
    ).timetuple()

    if start_date > end_date:
        flash("Start Date is later than End Date!")
        return False

    will_share = [claims]

    for r in request.args:
        if r.startswith("user"):
            will_share.append(request.args.get(r))

    if request.args.get("edit_event") == "edit_event":
        query = datastore_client.query(kind="event")
        query.add_filter("cal", "=", calname)
        query.add_filter("name", "=", event_name)
        fetched = list(query.fetch())

        for f in fetched:
            delete_row(
                "event",
                f["name"] + "_._" + f["cal"] + "_._" + f["creator"] + "_._" + f["user"],
            )

    # check for any clashes
    ts_start = time.mktime(start_date)
    ts_end = time.mktime(end_date)

    query = datastore_client.query(kind="event")
    query.add_filter("cal", "=", "personalCalendar")
    query.add_filter("user", "IN", will_share)
    fetched = list(query.fetch())
    print("query on events in add_event: ", fetched)
    for f in fetched:
        print("iter event: ", f)
        print("ts_start : ts_end", ts_start, " : ", ts_end)
        if ts_start >= f["end_date"] or ts_end <= f["start_date"]:
            continue
        else:
            flash("Event Clashes to one of personalCalendars and Can not shared.")
            return

    for u in will_share:
        create_row_from_data(
            "event",
            event_name + "_._" + calname + "_._" + claims + "_._" + u,
            {
                "name": event_name,
                "creator": claims,
                "start_date": time.mktime(start_date),
                "end_date": time.mktime(end_date),
                "notes": notes,
                "cal": calname,
                "user": u,
            },
        )

    flash("Event Added/Edited Successfully.")
    return will_share


def fill_mat(my_cals, week_info, selected_cals, claims):
    color_list = ["bg-warning", "bg-info", "bg-danger", "bg-primary", "bg-success"]
    event_mat = {}
    for hour in hours:
        event_mat[hour] = {}
        for wd in week_days_name:
            event_mat[hour][wd] = {}
            event_mat[hour][wd]["event_list"] = []

    if selected_cals == []:
        return

    result = {}
    for i in range(len(selected_cals)):
        calname, username = (
            selected_cals[i].split("_._")[0],
            selected_cals[i].split("_._")[1],
        )
        query = datastore_client.query(kind="event")
        query.add_filter("cal", "=", calname)
        query.add_filter("creator", "=", username)
        query.add_filter("user", "=", username)
        r = list(query.fetch())
        if r != None and r != [None] and r != []:
            for res in r:
                if username != claims:
                    res["event_shared_by"] = username
                result[res["name"] + res["creator"] + res["cal"]] = res
    # add direct shared cals to personalCalendar of user:
    query = datastore_client.query(kind="event")
    query.add_filter("cal", "=", "personalCalendar")
    query.add_filter("user", "=", claims)
    query.add_filter("creator", "!=", claims)
    r = list(query.fetch())
    if r != None and r != [None] and r != []:
        for res in r:
            res["directly_shared"] = "true"
            result[res["name"] + res["creator"] + res["cal"]] = res

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

    circular_counter = 0

    for event in result:
        start_t = datetime.datetime.fromtimestamp(result[event]["start_date"])
        end_t = datetime.datetime.fromtimestamp(result[event]["end_date"])
        result[event]["start_date"] = start_t.strftime("%Y-%m-%d")
        result[event]["end_date"] = end_t.strftime("%Y-%m-%d")
        result[event]["start_time"] = start_t.strftime("%H:%M")
        result[event]["end_time"] = end_t.strftime("%H:%M")
        result[event]["color"] = color_list[circular_counter]
        circular_counter += 1
        circular_counter = circular_counter % len(color_list)
        visit = "true"
        while start_t <= end_t:
            if start_t >= week_start and start_t <= week_end:
                weekday = week_days_name[start_t.weekday()]
                clock = start_t.strftime("%H:%M")
                result[event]["vis"] = visit
                event_mat[clock][weekday]["event_list"].append(result[event].copy())
            visit = "false"
            start_t += datetime.timedelta(minutes=30)

    return event_mat


def delete_cal(claims):
    if request.args.get("delete_cal") == None:
        return

    if request.args.get("owner") != claims:
        flash("You are not authorized to delete this calendar")
        return

    result = retrieve_row("cal", request.args.get("cal") + "_._" + claims)
    if result != None:
        for res in result["shared"]:
            user = retrieve_row("user", res)
            if user != None:
                shared_me = user["shared_me"].copy()
                for cals in user["shared_me"]:
                    if cals == (request.args.get("cal") + "_._" + claims):
                        del shared_me[request.args.get("cal") + "_._" + claims]
                user["shared_me"] = shared_me
                create_row_from_data("user", user["name"], user)

    query = datastore_client.query(kind="event")
    query.add_filter("cal", "=", result["name"])
    query.add_filter("creator", "=", result["owner"])
    fetched = list(query.fetch())
    for res in fetched:
        delete_row(
            "event",
            res["name"]
            + "_._"
            + res["cal"]
            + "_._"
            + res["creator"]
            + "_._"
            + res["user"],
        )

    delete_row("cal", request.args.get("cal") + "_._" + claims)
    flash("Calendar Deleted Successfully")


def delete_event(claims):
    if request.args.get("delete_event") == None:
        return

    if request.args.get("user") != claims:
        flash("You are not the creator of event!")
        return

    query = datastore_client.query(kind="event")
    query.add_filter("creator", "=", request.args.get("user"))
    query.add_filter("cal", "=", request.args.get("cal"))
    query.add_filter("name", "=", request.args.get("event"))
    fetched = list(query.fetch())

    for f in fetched:
        delete_row(
            "event",
            f["name"] + "_._" + f["cal"] + "_._" + f["creator"] + "_._" + f["user"],
        )
    flash("Event Deleted Successfully")


def delete_row(kind, name):
    key = datastore_client.key(kind, name)
    datastore_client.delete(key)


@app.route("/<dec_or_acc>/<sharedby>/<calname>")
def acc_or_dec_shared_cal(dec_or_acc, sharedby, calname):
    claims = get_session_info()

    result = query_result("name", "=", claims, "user")[0]
    if dec_or_acc == "accept":
        result["shared_me"][calname + "_._" + sharedby] = "yes"
        create_row_from_data("user", claims, result)
        return flash_redirect("Now the calendar is shared with you", "/")

    elif result["shared_me"].get(calname + "_._" + sharedby):
        del result["shared_me"][calname + "_._" + sharedby]
        create_row_from_data("user", claims, result)

        query = datastore_client.query(kind="cal")
        query.add_filter("owner", "=", sharedby)
        query.add_filter("name", "=", calname)
        fetched = list(query.fetch())[0]
        if fetched == []:
            return flash_redirect("Declined Successfully", "/")
        del fetched["shared"][claims]
        create_row_from_data("cal", calname + "_._" + sharedby, fetched)

        return flash_redirect("Declined Successfully", "/?cal_list_get=cal_list_get")
    else:
        return flash_redirect("No result found", "/?cal_list_get=cal_list_get")


@app.route("/stop_sharing_event/<eventname>/<calname>/<username>")
def stop_sharing_event(eventname, calname, username):
    claims = get_session_info()

    query = datastore_client.query(kind="event")
    query.add_filter("user", "=", username)
    query.add_filter("cal", "=", calname)
    query.add_filter("name", "=", eventname)
    fetched = list(query.fetch())[0]
    delete_row(
        "event",
        fetched["name"]
        + "_._"
        + fetched["cal"]
        + "_._"
        + fetched["creator"]
        + "_._"
        + fetched["user"],
    )
    return flash_redirect("Stopped Sharing this event with you", "/")


@app.route("/error")
def error():
    return render_template("50x.html")


@app.route("/", methods=["GET", "POST"])
def root():
    claims = get_session_info()

    if not claims:
        temp = render_template(
            "index.html",
            is_logged_in=False,
            pagename="Homepage",
        )
        resp = make_response(temp)
        resp.set_cookie("selected_date", "", expires=0)
        resp.set_cookie("selected_cals", "", expires=0)

        return resp

    delete_event(claims)
    delete_cal(claims)

    user_list = projection_on("user", "name")

    add_or_edit_calendar(claims)
    will_share = add_or_edit_event(claims)
    my_cals, selected_cals = get_my_cals(claims)

    week_info, selected_date, today, dominant_month = get_and_set_cal_week()

    event_mat = fill_mat(my_cals, week_info, list(selected_cals.keys()), claims)

    userinfo = query_result("name", "=", claims, "user")[0]

    temp = render_template(
        "index.html",
        today=today,
        wi=week_info,
        dominant_month=dominant_month,
        claims=claims,
        is_logged_in=True,
        my_cals=my_cals,
        user_list=user_list,
        userinfo=userinfo,
        hours=hours,
        will_share=will_share,
        event_mat=event_mat,
    )

    resp = make_response(temp)
    resp.set_cookie("selected_date", selected_date)
    resp.set_cookie("selected_cals", ",".join(list(selected_cals.keys())))

    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
