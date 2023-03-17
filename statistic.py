import plotly, locale, json, numpy as np, pandas as pd
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo

import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots

locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
MSK = ZoneInfo("Europe/Moscow")


def _get_statistic_file_html(data, user):
    df = pd.DataFrame(data).T.reset_index().rename(columns={'index':'days'})

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df['days'], y=df['correct'], name='correct'))
    fig.add_trace(go.Bar(x=df['days'], y=df['wrong'], name='wrong'))
    fig.add_trace(go.Bar(x=df['days'], y=df['correct']+df['wrong'], name='all'))
    fig.update_layout(
        legend_orientation="h",
        legend=dict(x=0.5, xanchor="center"),
        margin=dict(l=0, r=0, t=30, b=0),
        title=user.name,
        title_x=0.5,
        xaxis_title="Day",
        yaxis_title="Answer",
        )
    fig.update_traces(hoverinfo="all",hovertemplate="Day: %{x}<br>Aswers: %{y}")

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    file = open('example.html', 'w+b')
    html_doc = '''<!DOCTYPE html>
    <html lang="en">
    <head>
        <!-- Required meta tags -->
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.3.1/dist/css/bootstrap.min.css" integrity="sha384-ggOyR0iXCbMQv3Xipma34MD+dH/1fQ784/j6cY/iJTQUOhcWr7x9JvoRxT2MZw1T" crossorigin="anonymous">
        <title>You statistic</title>
    </head>
    <body>
        <div id="plotly_graph"></div>

        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/3.5.6/d3.min.js"></script>

        <script>var graphs = %s;</script>
        <script>Plotly.plot('plotly_graph',graphs,{});</script>
        
        <!-- Optional JavaScript -->
        <!-- jQuery first, then Popper.js, then Bootstrap JS -->
        <script src="https://code.jquery.com/jquery-3.3.1.slim.min.js" integrity="sha384-q8i/X+965DzO0rT7abK41JStQIAqVgRVzpbzo5smXKp4YfRvH+8abtTE1Pi6jizo" crossorigin="anonymous"></script>
        <script src="https://cdn.jsdelivr.net/npm/popper.js@1.14.7/dist/umd/popper.min.js" integrity="sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1" crossorigin="anonymous"></script>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@4.3.1/dist/js/bootstrap.min.js" integrity="sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM" crossorigin="anonymous"></script>
      

    </body>
    </html>''' % graphJSON

    file.write(html_doc.encode('utf-8'))
    file.seek(0)
    return file


def _today_filter(user):
    today = datetime.now(MSK).day
    new_data = {k.strftime("%d.%m.%Y"): user.stat[k] for k in user.stat if k.day == today}
    return new_data


def get_today_statistic(user):
    new_data = _today_filter(user)
    return _get_statistic_file_html(new_data, user)


def _month_filter(user):
    now = datetime.now(MSK).date()
    new_data = {k.strftime("%d.%m.%Y"): user.stat[k] for k in user.stat if now - k <= timedelta(days=30)}
    return new_data


def get_month_statistic(user):
    new_data = _month_filter(user)
    return _get_statistic_file_html(new_data, user)


