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
from flask import Blueprint
from plotly import graph_objs as go

from plotly import graph_objs as go
from plotly.graph_objs import *
from dash.dependencies import Input, Output, State

import flask

server = flask.Flask(__name__)


# app = dash.Dash(__name__)
# server = app.server
app.title = 'NYC 311 construction complaints'

#Blueprint error

# a random blueprint
from myblueprint import myblueprint as my_blueprint
#Close block

layout_map = dict(
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
    filter_statement = 'starts_with(complaint_type, "' + searchstr + '")' + \
                       ' and created_date > "' + start + '"' + \
                       ' and created_date < "' + end + '"' + \
                       ' and agency = "' + agency + '"' + \
                       ' and ' + str(range_str) + '(location, ' + str(location_data) + ')'
    select_statement = 'created_date,closed_date,agency,agency_name,complaint_type,descriptor,location_type,' \
                       'incident_zip,city,borough,' \
                       'status,due_date,latitude,' \
                       'longitude,location '

    results = client.get('erm2-nwe9',
                         limit=100000000,
                         where=filter_statement,
                         select=select_statement)
    complaints = pd.DataFrame.from_dict(results)

    complaints['created_date'] = pd.to_datetime(complaints['created_date'])
    complaints['created_date_wo_time'] = complaints['created_date'].apply(lambda x: x.date())
    complaints['lonlat'] = list(zip(complaints.longitude.astype(float), complaints.latitude.astype(float)))
    complaints['geometry'] = complaints[['lonlat']].applymap(lambda x: Point(x))
    crs = {'init': 'epsg:4326', 'no_defs': True}
    complaints = gpd.GeoDataFrame(complaints, crs=crs, geometry=complaints['geometry'])
    return (complaints)

# API keys and datasets
mapbox_access_token = 'pk.eyJ1Ijoic2lkZGFyZWRldmlsbCIsImEiOiJjazN6MDV5azEwMHRsM2tzMTVubGVxdWtiIn0.3btQ-Q2CuEQ_uuub-hAxvw'
map_data = return_complaint_data('2017-01-10T12:00:00','2018-01-10T12:00:00','Noise','DEP',1000,[[40.730928, -73.997665]])
map_data = map_data[['created_date_wo_time','borough','descriptor','latitude','longitude']]

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
                "mode": "markers",
                "name": list(map_data['descriptor']),
                "marker": {
                    "size": 6,
                    "opacity": 0.7
                }
        }],
        "layout": layout_map
    }

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
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets,server=server)

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
                                                 for item in set(map_data['descriptor'])],
                            multi=True,
                            value=list(set(map_data['descriptor']))
                        )
                    ],
                    className='six columns',
                    style={'margin-top': '10'}
                )
            ],
            className='row'
        ),
    # html.Div(children=[
    # html.H4(children='US Agriculture Exports (2011)'),
    # generate_table(map_data[:9])
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
    ),
        html.Div([
html.Div(
                    [
                        dcc.Graph(id='map-graph',
                                  animate=True,
                                  style={'margin-top': '20'})
                    ], className = "six columns"
                ),
#Testing
html.Div(
                    [
                        dcc.Graph(id='bar-graph',
                                  animate=True,
                                  style={'margin-top': '20'})
                    ], className = "six columns"
                ),
#Testing block closed
        ],className='row'),
#Testing block
html.Div([html.Div(
    [
            dcc.Graph(id='bar-graph1',
            animate=True,
            style={'margin-top': '20'})
    ],className='row'
)])
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
    map_aux = map_aux[map_aux["descriptor"].isin(type)]
    map_aux = map_aux[map_aux["borough"].isin(borough)]

    rows = map_aux.to_dict('records')
    return rows

@app.callback(
    Output('map-graph', 'figure'),
    [Input('datatable', 'data'),
     Input('datatable', 'selected_rows')])
def map_selection(rows, selected_row_indices):
    aux = pd.DataFrame(rows)
    print(selected_row_indices)
    if selected_row_indices is None:
        print("passed through")
        return gen_map(aux)
    elif len(selected_row_indices) == 0:
        print("passed through")
        return gen_map(aux)
    else:
        print("reached here")
        temp_df = aux[aux.index.isin(selected_row_indices)]
        return gen_map(temp_df)

@app.callback(
    Output('bar-graph', 'figure'),
    [Input('datatable', 'data'),
     Input('datatable', 'selected_rows')])
def update_figure(rows, selected_row_indices):

    if selected_row_indices is None:
        dff = pd.DataFrame(rows)
    else:
        temp_df = pd.DataFrame(rows)
        dff = temp_df[temp_df.index.isin(selected_row_indices)]


    layout = go.Layout(
        bargap=0.05,
        bargroupgap=0,
        barmode='group',
        showlegend=False,
        dragmode="select",
        title='Complaints grouped by descriptor',
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
             x=dff.groupby('descriptor', as_index = False).count()['descriptor'],
             y=dff.groupby('descriptor', as_index = False).count()['latitude']
         )
     ])

    return go.Figure(data=data, layout=layout)

@app.callback(
    Output('bar-graph1', 'figure'),
    [Input('map-graph', 'selectedData'),
     Input('datatable', 'data')])
def update_figure(rows,dataframe):
    aux = pd.DataFrame(dataframe)
    print(rows)
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


if __name__ == '__main__':
    app.run_server(debug=False)