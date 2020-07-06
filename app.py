import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_table_experiments as dt
import dash_table
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, MultiPoint
from sodapy import Socrata
from flask_caching import Cache
from datetime import datetime
import dateutil.relativedelta
import json
import urllib.request
from shapely.wkt import loads
from fiona.crs import from_epsg



from plotly import graph_objs as go
from plotly.graph_objs import *
from dash.dependencies import Input, Output, State

import flask



# app = dash.Dash(__name__)
# server = app.server

#Blueprint error

# a random blueprint
from myblueprint import myblueprint as my_blueprint
#Close block

layout_map = dict(
    showlegend=False,
    autosize=True,
    height=500,
    font=dict(color="#191A1A"),
    titlefont=dict(color="#191A1A", size='14'),
    margin=dict(
        l=35,
        r=35,
        b=35,
        t=45
    ),
    hovermode="closest",
    # plot_bgcolor='#fffcfc',
    # paper_bgcolor='#fffcfc',
    legend=dict(font=dict(size=10), orientation='h'),
    title='Map of 311 complaints',
    mapbox=dict(
        accesstoken='pk.eyJ1Ijoic2lkZGFyZWRldmlsbCIsImEiOiJjazN6MDV5azEwMHRsM2tzMTVubGVxdWtiIn0.3btQ-Q2CuEQ_uuub-hAxvw',
        style="light",
        center=dict(
            lon=-73.99226736786993,
            lat=40.7342
        ),
        zoom=11,
    )
)

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

app.title = 'NYC 311 construction complaints'


cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory'
})

@cache.memoize(timeout=60*60)
def return_complaint_data(start=None, end=None, searchstr='Noise', agency='DEP', radius=100, points=[[0, 0]]):
    client = Socrata('data.cityofnewyork.us', 'XDub3WPSwRBGDfcIXVLm43O32')
    points = np.array(points)
    if points.shape[0] == 1:
        range_str = 'within_circle'
        location_data = str(points[0][0]) + ', ' + str(points[0][1]) + ', ' + str(radius)
    else:
        range_str = 'within_polygon'
        location_data = '"MULTIPOLYGON ((('
        points[-1] = points[0]
        for point in points:
            location_data = location_data + str(point[0]) + ' ' + str(point[1]) + ', '
        location_data = location_data[0:-2]
        location_data = location_data + ')))"'

    now = datetime.now()
    current_time = now.strftime("%Y-%m-%dT%H:%M:%S")
    earlier_time = (now - dateutil.relativedelta.relativedelta(months=2)).strftime("%Y-%m-%dT%H:%M:%S")
    filter_statement = 'starts_with(complaint_type, "' + searchstr + '")' + \
                       ' and created_date > "' + earlier_time + '"' + \
                       ' and created_date < "' + current_time + '"' + \
                       ' and agency = "' + agency + '"' #+ \
                       #' and ' + str(range_str) + '(location, ' + str(location_data) + ')'
    select_statement = 'created_date,descriptor,' \
                       'borough,' \
                       'latitude,' \
                       'longitude'

    # select_statement = 'created_date,closed_date,agency,agency_name,complaint_type,descriptor,location_type,' \
    #                    'incident_zip,city,borough,' \
    #                    'status,due_date,latitude,' \
    #                    'longitude,location '

    results = client.get('erm2-nwe9',
                         limit=100000000,
                         where=filter_statement,
                         select=select_statement)
    complaints = pd.DataFrame.from_dict(results)

    complaints['complaint_code'] = complaints['descriptor'].apply(lambda x: x.split(' ')[-1].strip('(').strip(')'))
    complaints['cleaned_descriptor'] = complaints['descriptor'].apply(lambda x: x.replace('Noise: ','').replace('Noise, ',''))
    complaints['created_date'] = pd.to_datetime(complaints['created_date'])
    complaints['created_date_wo_time'] = complaints['created_date'].apply(lambda x: x.date())
    complaints['lonlat'] = list(zip(complaints.longitude.astype(float), complaints.latitude.astype(float)))
    complaints['geometry'] = complaints[['lonlat']].applymap(lambda x: Point(x))
    crs = {'init': 'epsg:4326', 'no_defs': True}
    complaints = gpd.GeoDataFrame(complaints, crs=crs, geometry=complaints['geometry'])
    return (complaints)

@cache.memoize(timeout=60*60)
def return_construction_permits():
    now = datetime.now()
    date_to = now.strftime("%m/%d/%Y")
    date_from = (now - dateutil.relativedelta.relativedelta(months=2)).strftime("%m/%d/%Y")
    print("Date in construction permit function is " + str(date_to))

    # date_from = '01/01/2020'
    # date_to = '04/18/2020'
    ret_row_num = 99999999999999999

    link = 'https://nycstreets.net/Public/Permit/SearchPermits/?' \
           'PermitIssueDateFrom=' + date_from + \
           '&PermitIssueDateTo=' + date_to + \
           '&rows=' + str(ret_row_num) + \
           '&sidx=PermitIssueDateFrom' \
           '&sord=desc' \
           '&LocationSearchType=0'
    f = json.loads(urllib.request.urlopen(link).read())
    permit_data = pd.DataFrame.from_dict(f['PermitList'])
    permit_data['geometry'] = permit_data['Wkt'].apply(lambda x: loads(x))
    permit_data_gdf = gpd.GeoDataFrame(permit_data, geometry='geometry')
    permit_data_gdf.crs = from_epsg(2263)
    permit_data_gdf = permit_data_gdf.to_crs(epsg=4326)
    return(permit_data_gdf)


# API keys and datasets
cache.clear()
mapbox_access_token = 'pk.eyJ1Ijoic2lkZGFyZWRldmlsbCIsImEiOiJjazN6MDV5azEwMHRsM2tzMTVubGVxdWtiIn0.3btQ-Q2CuEQ_uuub-hAxvw'
map_data = return_complaint_data('2017-01-10T12:00:00','2018-01-10T12:00:00','Noise','DEP',1000,[[40.730928, -73.997665]])
map_data = map_data[['created_date_wo_time','borough','descriptor','latitude','longitude','complaint_code'
    ,'cleaned_descriptor']]
permit_data_gdf = return_construction_permits()
test_df = pd.DataFrame([['tom', 25], ['krish', 30],
       ['nick', 26], ['juli', 22]] , columns =['Name', 'Age'])
programmers = ['Alex','Nicole','Sara','Etienne','Chelsea','Jody','Marianne']

base = datetime.today()
dates = map_data['created_date_wo_time']
z = np.random.poisson(size=(len(programmers), len(dates)))
heatmap = go.Figure(data=go.Heatmap(
        z=z,
        x=dates,
        y=programmers,
        colorscale='Viridis'))
print(map_data.head())



def gen_map(map_data):
    # groupby returns a dictionary mapping the values of the first field
    # 'classification' onto a list of record dictionaries with that
    # classification value.
    return {
        "data": [{
                "type": "scattermapbox",
                "lat": list(map_data['latitude']),
                "lon": list(map_data['longitude']),
                "hoverinfo": "text",
                "hovertext": [["Descriptor: {} <br>Created Date: {}".format(i,j)]
                                for i,j in zip(map_data['descriptor'], map_data['created_date_wo_time'])],
                "mode": "markers+lines",
                "name": list(map_data['descriptor']),
                "marker": {
                    "size": 4,
                    "opacity": 0.3
                },
                "selected":{
                    "marker":{
                        "color":'red'
                    }
                }

        }],
        "layout": layout_map
    }

def gen_lines(lat, lon, map_data, start_date = None, end_date = None):
    # groupby returns a dictionary mapping the values of the first field
    # 'classification' onto a list of record dictionaries with that
    # classification value.

    main_dict_list = []
    individual_dict = {}
    hyperlink_format = '<a href="{link}">{text}</a>'

    for index, i in permit_data_gdf.iterrows():
        if (i.geometry.type == 'LineString'):
            individual_dict = {}
            latitude = []
            longitude = []
            for pt in i.geometry.coords:
                latitude.append(Point(pt).y)
                longitude.append(Point(pt).x)
            # Dict input block start
            individual_dict["type"] = "scattermapbox"
            individual_dict["lat"] = latitude
            individual_dict["lon"] = longitude
            individual_dict["hoverinfo"] = "text"
            individual_dict["hovertext"] = [hyperlink_format.format(
                link="https://nycstreets.net/Public/Document/ViewPermitPDF/?id=" + i.PermitNumber, text='View PDF')]
            individual_dict["mode"] = "markers+lines"
            individual_dict["line"] = {"color": '#2ca02c', "width": 15}
            individual_dict["marker"] = {
                    "color": '#2ca02c',
                    "size": 15,
                    "opacity": 1
                }
            individual_dict["selected"] = {
                    "lines": {
                        "color": 'red'
                    }
                }
            main_dict_list.append(individual_dict)
        elif (i.geometry.type == 'MultiLineString'):
            hyperlink_format = '<a href="{link}">{text}</a>'
            for line in i.geometry:
                latitude = []
                longitude = []
                for pt in line.coords:
                    latitude.append(Point(pt).y)
                    longitude.append(Point(pt).x)
                individual_dict["type"] = "scattermapbox"
                individual_dict["lat"] = latitude
                individual_dict["lon"] = longitude
                individual_dict["hoverinfo"] = "text"
                individual_dict["hovertext"] = [hyperlink_format.format(link="https://nycstreets.net/Public/Document/ViewPermitPDF/?id=" + i.PermitNumber, text='View PDF')]
                individual_dict["mode"] = "markers+lines"
                individual_dict["line"] = {"color": '#2ca02c', "width": 15}
                individual_dict["marker"] = {
                    "color": '#2ca02c',
                    "size": 15,
                    "opacity": 1
                }
                individual_dict["selected"] = {
                    "marker": {
                        "color": 'red'
                    }
                }
                main_dict_list.append(individual_dict)
        elif (i.geometry.type == 'Point'):
            hyperlink_format = '<a href="{link}">{text}</a>'
            individual_dict["type"] = "scattermapbox"
            individual_dict["lat"] = [Point(i.geometry).y]
            individual_dict["lon"] = [Point(i.geometry).x]
            individual_dict["hoverinfo"] = "text"
            individual_dict["hovertext"] = [hyperlink_format.format(link="https://nycstreets.net/Public/Document/ViewPermitPDF/?id=" + i.PermitNumber, text='View PDF')]
            individual_dict["mode"] = "markers"
            individual_dict["marker"] = {
                    "color": '#2ca02c',
                    "size": 8,
                    "opacity": 1
                }
            individual_dict["selected"] = {
                    "marker": {
                        "color": 'red'
                    }
                }
            main_dict_list.append(individual_dict)
            # Dict input block close

    if start_date is not None:
        map_data = map_data[(map_data['created_date_wo_time'] >= start_date) &
                            (map_data['created_date_wo_time'] <= end_date)]
    complaints_dict = {}
    complaints_dict["type"] = "scattermapbox"
    complaints_dict["lat"] = list(map_data['latitude'])
    complaints_dict["lon"] = list(map_data['longitude'])
    complaints_dict["hoverinfo"] = "text"
    complaints_dict["hovertext"] = [["Descriptor: {} <br>Created Date: {}".format(i, j)]
                              for i, j in zip(map_data['descriptor'], map_data['created_date_wo_time'])]
    complaints_dict["mode"] = "markers"
    complaints_dict["marker"] = {
        "color": '#1f77b4',
        "size": 4,
        "opacity": 0.3
    }
    complaints_dict["selected"] = {
        "marker": {
            "color": 'red'
        }
    }


    main_dict_list.append(complaints_dict)

    return{"data": main_dict_list, "layout": layout_map}

    # Working return statement
    # return {
    #     "data": [{
    #             "type": "scattermapbox",
    #             "lat": lat,
    #             "lon": lon,
    #             "hoverinfo": "text",
    #             "mode": "lines",
    #             "line":{"color":"MediumPurple", "width": 13},
    #             "marker": {
    #                 "size": 15,
    #                 "opacity": 0.7
    #             },
    #             "selected":{
    #                 "marker":{
    #                     "color":'red'
    #                 }
    #             }
    #
    #     },
    #         {
    #             "type": "scattermapbox",
    #             "lat": [40.72135363269204, 40.72174410248905],
    #             "lon": [-74.0046351627455, -74.00522716172279],
    #             "hoverinfo": "text",
    #             "mode": "lines",
    #             "line": {"color": "MediumPurple"},
    #             "marker": {
    #                 "size": 15,
    #                 "opacity": 0.7
    #             },
    #             "selected": {
    #                 "marker": {
    #                     "color": 'red'
    #                 }
    #             },
    #
    #         },
    #         {
    #             "type": "scattermapbox",
    #             "lat": list(map_data['latitude']),
    #             "lon": list(map_data['longitude']),
    #             "hoverinfo": "text",
    #             "hovertext": [["Descriptor: {} <br>Created Date: {}".format(i, j)]
    #                           for i, j in zip(map_data['descriptor'], map_data['created_date_wo_time'])],
    #             "mode": "markers",
    #             "name": list(map_data['descriptor']),
    #             "marker": {
    #                 "size": 6,
    #                 "opacity": 0.7
    #             },
    #             "selected": {
    #                 "marker": {
    #                     "color": 'red'
    #                 }
    #             }
    #
    #         }
    #     ],
    #     "layout": layout_map
    # }

def generate_table(dataframe, max_rows=10):
    return html.Table(
        # Header
        [html.Tr([html.Th(col) for col in dataframe.columns])] +

        # Body
        [html.Tr([
            html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
        ]) for i in range(min(len(dataframe), max_rows))]
    )
# Selecting only required columns

# Boostrap CSS.
# app.css.append_css({'external_url': 'https://codepen.io/amyoshino/pen/jzXypZ.css'})



layout_table = dict(
    autosize=True,
    height=500,
    font=dict(color="#191A1A"),
    titlefont=dict(color="#191A1A", size='14'),
    margin=dict(
        l=35,
        r=35,
        b=35,
        t=45
    ),
    hovermode="closest",
    plot_bgcolor='#fffcfc',
    paper_bgcolor='#fffcfc',
    legend=dict(font=dict(size=10), orientation='h'),
)
layout_table['font-size'] = '12'
layout_table['margin-top'] = '20'

app.layout = html.Div(
    html.Div([
        html.Div(
            [
                html.H1(children='311 Construction complaints',
                        className='nine columns'),

                html.Div(children='''
                        
                        ''',
                        className='nine columns'
                )
            ], className="row"
        ),

        # Selectors
        html.Div(
            [
                html.Div(
                    [
                        html.P('Choose Boroughs:'),
                        dcc.Checklist(
                                id = 'boroughs',
                                options=[
                                    {'label': 'Manhattan', 'value': 'MANHATTAN'},
                                    {'label': 'Bronx', 'value': 'BRONX'},
                                    {'label': 'Queens', 'value': 'QUEENS'},
                                    {'label': 'Brooklyn', 'value': 'BROOKLYN'},
                                    {'label': 'Staten Island', 'value': 'STATEN ISLAND'}
                                ],
                                value=['MANHATTAN', 'BRONX', "QUEENS",  'BROOKLYN', 'STATEN ISLAND'],
                                labelStyle={'display': 'inline-block'}
                        ),
                    ],
                    className='six columns',
                    style={'margin-top': '10'}
                ),
                html.Div(
                    [
                        html.P('Type:'),
                        dcc.Dropdown(
                            id='type',
                            options= [{'label': str(item),
                                                  'value': str(item)}
                                                 for item in set(map_data['cleaned_descriptor'])],
                            multi=True,
                            value=list(set(map_data['cleaned_descriptor']))
                        )
                    ],
                    className='six columns',
                    style={'margin-top': '10'}
                )
            ],
            className='row'
        ),


        html.Div([
html.Div(
                    [
                        dcc.Graph(id='map-graph',
                                  animate=False,
                                  style={'margin-top': '20'})
                    ], className="six columns"
                ),
#Testing
            html.Div([
                dcc.Graph(id='heatmap')
                # dash_table.DataTable(
                #     id='datatable1',
                #     columns=[{"name": i, "id": i} for i in test_df.columns],
                #     data=test_df.to_dict('records'),
                #     style_table={ 'height': 'auto',
                #         'overflowY': 'scroll',
                #         'margin-top': '20'
                #     })
                     ], className= "six columns"
            )
#Testing block closed
        ],className='row',
        style = {"margin-top":20}),
#Testing block
html.Div([html.Div(
    [
            dcc.Graph(id='bar-graph1',
            animate=False,
            style={'margin-top': '20'})
    ],className='six columns'
),
html.Div(
    [
        dcc.Graph(id='bar-graph',
                  animate=False,
                  style={'margin-top': '20'})
    ], className="six columns"
)],className='row'),
html.Div(
    dash_table.DataTable(
    id='datatable',
    columns=[{"name": i, "id": i} for i in map_data.columns],
    data=map_data.to_dict('records'),
    row_selectable='multi',
    style_table={
        'maxHeight': '300px',
        'overflowY': 'scroll'
    }
)
                )
#Testing block closed
]))

@app.callback(
    Output('datatable', 'data'),
    [Input('type', 'value'),
     Input('boroughs', 'value')])
def update_selected_row_indices(type, borough):
    map_aux = map_data.copy()

    # Type filter
    #map_aux = map_aux[map_aux['Type'].isin(type)]
    # Boroughs filter
    map_aux = map_aux[map_aux["cleaned_descriptor"].isin(type)]
    map_aux = map_aux[map_aux["borough"].isin(borough)]

    rows = map_aux.to_dict('records')
    return rows

# @app.callback(
#     Output('datatable1', 'data'),
#     [Input('boroughs', 'value')])
# def update_selected_row_indices1(borough):
#     rows = test_df.to_dict('records')
#     return rows


@app.callback(
    Output('map-graph', 'figure'),
    [Input('datatable', 'data'),
     Input('datatable', 'selected_rows'),
     Input('bar-graph1', 'selectedData'),
     Input('heatmap', 'relayoutData')])
def map_selection(rows, selected_row_indices, date_filter, heatmap_filter):
    if date_filter is None:
        aux = pd.DataFrame(rows)
        if selected_row_indices is None:
            return gen_lines([40.71626221912999,40.71638549163064,40.71659288087297,40.71697279046784,40.71716166759111],
                          [-73.80183790285439,-73.80099807258648,-73.8000012064612,-73.79864308775468,-73.79796193139329],aux)
        elif len(selected_row_indices) == 0:
            return gen_lines([40.71626221912999,40.71638549163064,40.71659288087297,40.71697279046784,40.71716166759111],
                          [-73.80183790285439,-73.80099807258648,-73.8000012064612,-73.79864308775468,-73.79796193139329],aux)
        else:
            temp_df = aux[aux.index.isin(selected_row_indices)]
            return gen_lines([40.71626221912999,40.71638549163064,40.71659288087297,40.71697279046784,40.71716166759111],
                          [-73.80183790285439,-73.80099807258648,-73.8000012064612,-73.79864308775468,-73.79796193139329],temp_df)
    else:
        print(date_filter)
        if heatmap_filter is None:
            pass
        else:
            print('Heatmap selected ' + str(heatmap_filter))
            heatmap_selected_startdate = str(dict(heatmap_filter)['xaxis.range[0]']).split(' ')[0]
            heatmap_selected_enddate = str(dict(heatmap_filter)['xaxis.range[1]']).split(' ')[0]
            print(heatmap_selected_startdate)
        aux = pd.DataFrame(rows)
        selected_dates = [(point["x"]) for point in date_filter["points"]]
        print()
        if selected_row_indices is None:
            return gen_lines(
                [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
                [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
                aux, min(selected_dates), max(selected_dates))
            # return gen_lines(
            #     [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
            #     [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
            #     aux, heatmap_selected_startdate, heatmap_selected_enddate)
        elif len(selected_row_indices) == 0:
            return gen_lines(
                [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
                [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
                aux, min(selected_dates), max(selected_dates))
            # return gen_lines(
            #     [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
            #     [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
            #     aux, heatmap_selected_startdate, heatmap_selected_enddate)
        else:
            temp_df = aux[aux.index.isin(selected_row_indices)]
            return gen_lines(
                [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
                [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
                temp_df, min(selected_dates), max(selected_dates))
            # return gen_lines(
            #     [40.71626221912999, 40.71638549163064, 40.71659288087297, 40.71697279046784, 40.71716166759111],
            #     [-73.80183790285439, -73.80099807258648, -73.8000012064612, -73.79864308775468, -73.79796193139329],
            #     temp_df, heatmap_selected_startdate, heatmap_selected_enddate)
# @app.callback(
#     Output('bar-graph', 'figure'),
#     [Input('datatable', 'data'),
#      Input('datatable', 'selected_rows')])
# def update_figure(rows, selected_row_indices):
#
#     if selected_row_indices is None:
#         dff = pd.DataFrame(rows)
#     else:
#         temp_df = pd.DataFrame(rows)
#         dff = temp_df[temp_df.index.isin(selected_row_indices)]
#
#
#     layout = go.Layout(
#         bargap=0.05,
#         bargroupgap=0,
#         barmode='group',
#         showlegend=False,
#         dragmode="select",
#         title='Complaints grouped by descriptor',
#         xaxis=dict(
#             showgrid=False,
#             nticks=50,
#             fixedrange=False
#         ),
#         yaxis=dict(
#             showticklabels=True,
#             showgrid=False,
#             fixedrange=False,
#             rangemode='nonnegative',
#             zeroline=True
#         )
#     )
#
#     data = Data([
#          go.Bar(
#              x=dff.groupby('complaint_code', as_index = False).count()['complaint_code'],
#              y=dff.groupby('complaint_code', as_index = False).count()['latitude']
#          )
#      ])
#
#     return go.Figure(data=data, layout=layout)

@app.callback(
    Output('bar-graph', 'figure'),
    [Input('map-graph', 'selectedData'),
     Input('datatable', 'data')])
def update_figure(rows, dataframe):
    aux = pd.DataFrame(dataframe)
    if rows is None:
        temp_df = aux
    else:
        selected_row_indices = []
        for i in rows['points']:
            selected_row_indices.append(i['pointIndex'])

        temp_df = aux[aux.index.isin(selected_row_indices)]
    layout = go.Layout(
        bargap=0.05,
        bargroupgap=0,
        barmode='group',
        showlegend=False,
        title='Complaints grouped by type',
        dragmode="select",
        xaxis=dict(
            showticklabels=False,
            showgrid=False,
            nticks=50,
            fixedrange=False
        ),
        yaxis=dict(
            showticklabels=True,
            showgrid=False,
            fixedrange=False,
            rangemode='nonnegative',
            zeroline=True
        )
    )

    data = Data([
         go.Bar(
             x=temp_df.groupby('cleaned_descriptor', as_index = False).count().sort_values(by=['latitude'],ascending=True)['latitude'],
             y=temp_df.groupby('cleaned_descriptor', as_index = False).count().sort_values(by=['latitude'],ascending=True)['cleaned_descriptor'],
             orientation='h',
             text=temp_df.groupby('cleaned_descriptor', as_index = False).count().sort_values(by=['latitude'],ascending=True)['latitude'],
             textposition='auto'
         )
     ])

    return go.Figure(data=data, layout=layout)

# @app.callback(
#     Output('summary1', 'children'),
#     [Input('map-graph', 'selectedData')])
# def update_summary1(rows):
#     if rows is None:
#         return("The number of street permits are " + str(len(permit_data_gdf)))
#     else:
#         selected_row_indices = []
#         for i in rows['points']:
#             selected_row_indices.append(i['pointIndex'])
#         print("The number of selected street permits are ")
#         print(permit_data_gdf[permit_data_gdf.index.isin(selected_row_indices)]['PermitNumber'])
#         return("The number of street permits are " +str(len(permit_data_gdf[permit_data_gdf.index.isin(selected_row_indices)].drop_duplicates(subset=['PermitNumber']))))
#
# @app.callback(
#     Output('summary2', 'children'),
#     [Input('map-graph', 'selectedData')])
# def update_summary2(rows):
#     if rows is None:
#         return ("The number of complaints are " + str(len(map_data)))
#     else:
#         selected_row_indices = []
#         for i in rows['points']:
#             selected_row_indices.append(i['pointIndex'])
#
#         temp_df = map_data[map_data.index.isin(selected_row_indices)]
#         return("The number of complaints are" + str(len(temp_df)))


@app.callback(
    Output('bar-graph1', 'figure'),
    [Input('map-graph', 'selectedData'),
     Input('datatable', 'data')])
def update_figure(rows,dataframe):
    aux = pd.DataFrame(dataframe)
    if rows is None:
        temp_df = aux
    else:
        selected_row_indices = []
        for i in rows['points']:
            selected_row_indices.append(i['pointIndex'])

        temp_df = aux[aux.index.isin(selected_row_indices)]
    layout = go.Layout(
        bargap=0.05,
        bargroupgap=0,
        barmode='group',
        showlegend=False,
        title='Complaints grouped by date',
        dragmode="select",
        xaxis=dict(
            showgrid=False,
            nticks=50,
            fixedrange=False
        ),
        yaxis=dict(
            showticklabels=True,
            showgrid=False,
            fixedrange=False,
            rangemode='nonnegative',
            zeroline=True
        )
    )

    data = Data([
         go.Bar(
             x=temp_df.groupby('created_date_wo_time', as_index = False).count()['created_date_wo_time'],
             y=temp_df.groupby('created_date_wo_time', as_index = False).count()['latitude']
         )
     ])

    return go.Figure(data=data, layout=layout)

@app.callback(
    Output('heatmap', 'figure'),
    [Input('map-graph', 'selectedData'),
    Input('map-graph', 'relayoutData'),
     Input('datatable', 'data')])
def update_figure(rows, x, dataframe):
    try:
        latitude = [float(i[1]) for i in dict(x)['mapbox._derived']['coordinates']]
        longitude = [float(i[0]) for i in dict(x)['mapbox._derived']['coordinates']]
        aux = pd.DataFrame(dataframe)
        aux.dropna(subset=['latitude'],inplace=True)
        aux['latitude'] = aux['latitude'].apply(lambda rec: float(rec))
        aux['longitude'] = aux['longitude'].apply(lambda rec: float(rec))
        aux = aux[(aux['latitude'] > min(latitude)) & (aux['latitude'] < max(latitude)) &
                  (aux['longitude'] > min(longitude)) & (aux['longitude'] < max(longitude))]

    except:
        aux = pd.DataFrame(dataframe)
        pass

    if rows is None:
        temp_df = aux
    else:
        selected_row_indices = []
        for i in rows['points']:
            selected_row_indices.append(i['pointIndex'])

        temp_df = aux[aux.index.isin(selected_row_indices)]
    layout = go.Layout(
        bargap=0.05,
        bargroupgap=0,
        barmode='group',
        showlegend=False,
        title='Complaints grouped by date',
        dragmode="select",
        xaxis=dict(
            showgrid=False,
            nticks=50,
            fixedrange=False
        ),
        yaxis=dict(
            showticklabels=True,
            showgrid=False,
            fixedrange=False,
            rangemode='nonnegative',
            zeroline=True
        )
    )


    def df_to_plotly(df):
        ref_df = df.groupby(by=['created_date_wo_time', 'complaint_code']).count().reset_index()[
            ['created_date_wo_time', 'complaint_code', 'latitude']]
        filling_records_df = pd.DataFrame(columns=['created_date_wo_time', 'complaint_code', 'latitude'])
        for i in ref_df['created_date_wo_time'].unique():
            for j in ref_df['complaint_code'].unique():
                filling_records_df = filling_records_df.append(
                    {'created_date_wo_time': i, 'complaint_code': j, 'latitude': 0}, ignore_index=True)
        filled_df = pd.concat([ref_df, filling_records_df]).groupby(
            by=['created_date_wo_time', 'complaint_code']).sum().reset_index()
        return {'z': filled_df['latitude'].tolist(),
                'x': filled_df['created_date_wo_time'].tolist(),
                'y': filled_df['complaint_code'].tolist()}
    heatmap1 = go.Figure(data=go.Heatmap(df_to_plotly(temp_df)),
                         layout=go.Layout(title='Heatmap'))
    return heatmap1



if __name__ == '__main__':
    app.run_server(debug=False)