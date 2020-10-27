import dash
from textwrap import dedent
import time
import dash_core_components as dcc
import dash_html_components as html
import sys
sys.path.insert(0, 'D:/Documents/wsp_mini_project/dash_application-line_segments -time - Copy/secrets_file')
import secrets_file
import dash_table_experiments as dt
import dash_gif_component as Gif
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
import dash_bootstrap_components as dbc
from plotly import graph_objs as go
from plotly.graph_objs import *
from dash.dependencies import Input, Output, State
import flask
from myblueprint import myblueprint as my_blueprint

# Close block

# Dictionary containing the map's layout
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
        accesstoken=secrets_file.mapbox_access_token,
        style="light",
        center=dict(
            lon=-73.99226736786993,
            lat=40.7342
        ),
        zoom=11,
    )
)

external_stylesheets = [dbc.themes.BOOTSTRAP, 'https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server

app.title = 'NYC 311 construction complaints'

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory'
})


@cache.memoize(timeout=60 * 60)
def return_complaint_data(searchstr='Noise', agency='DEP', radius=100, points=[[0, 0]]):
    '''
    This funtion calls the socrata API for 311 complaints and creates the geodataframe required for the dashboard.
    The function is cached and updates every hour.
    :param searchstr: Filtering the complaint type in the API call, this can be Air, Noise etc
    :param agency: Filtering the agency in the API call
    :param radius: Specifying the radius in miles
    :param points: Passing the centre of the circle in latitude and longitude
    :return: The geodataframe holding the cleaned fields
    '''
    client = Socrata('data.cityofnewyork.us', secrets_file.socrata_key)
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
                       ' and agency = "' + agency + '"'

    select_statement = 'created_date,descriptor,' \
                       'borough,' \
                       'latitude,' \
                       'longitude'

    results = client.get(secrets_file.socrata_user_key,
                         limit=100000000,
                         where=filter_statement,
                         select=select_statement)
    complaints = pd.DataFrame.from_dict(results)

    complaints['complaint_code'] = complaints['descriptor'].apply(lambda x: x.split(' ')[-1].strip('(').strip(')'))
    complaints['cleaned_descriptor'] = complaints['descriptor'] \
        .apply(lambda x: x.replace('Noise: ', '').replace('Noise, ', '').strip(' '))
    complaints['created_date'] = pd.to_datetime(complaints['created_date'])
    complaints['created_date_wo_time'] = complaints['created_date'].apply(lambda x: x.date())
    complaints['lonlat'] = list(zip(complaints.longitude.astype(float), complaints.latitude.astype(float)))
    complaints['geometry'] = complaints[['lonlat']].applymap(lambda x: Point(x))
    crs = {'init': 'epsg:4326', 'no_defs': True}
    complaints = gpd.GeoDataFrame(complaints, crs=crs, geometry=complaints['geometry'])
    return (complaints)


@cache.memoize(timeout=60 * 60)
def return_construction_permits():
    '''
    This function is used to get the street construction permits.
    The function is cached and updates every hour.
    :return: The geodataframe holding the street construction permits
    '''
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
    permit_data = permit_data[permit_data['Wkt'].notnull()]
    permit_data['geometry'] = permit_data['Wkt'].apply(lambda x: loads(x))
    permit_data_gdf = gpd.GeoDataFrame(permit_data, geometry='geometry')
    permit_data_gdf.crs = from_epsg(2263)
    permit_data_gdf = permit_data_gdf.to_crs(epsg=4326)
    return (permit_data_gdf)


# API keys and datasets
cache.clear()
mapbox_access_token = secrets_file.mapbox_access_token
map_data = return_complaint_data('Noise', 'DEP', 1000,
                                 [[40.730928, -73.997665]])
map_data = map_data[['created_date_wo_time', 'borough', 'descriptor', 'latitude', 'longitude', 'complaint_code'
                    , 'cleaned_descriptor']]
permit_data_gdf = return_construction_permits()
print(map_data.head())


def gen_map(map_data):
    '''
    Create the dictionary to display the noise complaints points using dash.
    :param map_data: Geodataframe with location data of the noise complaints
    :return: The dictionary that is used for showing this information on dash
    '''
    # groupby returns a dictionary mapping the values of the first field
    # 'classification' onto a list of record dictionaries with that
    # classification value.
    return {
        "data": [{
            "type": "scattermapbox",
            "lat": list(map_data['latitude']),
            "lon": list(map_data['longitude']),
            "hoverinfo": "text",
            "hovertext": [["Descriptor: {} <br>Created Date: {}".format(i, j)]
                          for i, j in zip(map_data['descriptor'], map_data['created_date_wo_time'])],
            "mode": "markers+lines",
            "name": list(map_data['descriptor']),
            "marker": {
                "size": 4,
                "opacity": 0.3
            },
            "selected": {
                "marker": {
                    "color": 'red'
                }
            }

        }],
        "layout": layout_map
    }


def gen_lines(map_data, start_date=None, end_date=None):
    '''
    Convert street construction permits data frame into a dictionary to display on the map using dash.
    This function converts multi-lines and lines into points which are visualized.
    :param map_data: Geodataframe containing the street construction permits.
    :param start_date:
    :param end_date:
    :return: A dictionary containing the street permits that are visualized using dash.
    '''
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
            individual_dict["line"] = {"color": '#2ca02c', "width": 10}
            individual_dict["marker"] = {
                "color": '#2ca02c',
                "size": 10,
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
                individual_dict["hovertext"] = [hyperlink_format.format(
                    link="https://nycstreets.net/Public/Document/ViewPermitPDF/?id=" + i.PermitNumber, text='View PDF')]
                individual_dict["mode"] = "markers+lines"
                individual_dict["line"] = {"color": '#2ca02c', "width": 10}
                individual_dict["marker"] = {
                    "color": '#2ca02c',
                    "size": 10,
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
            individual_dict["hovertext"] = [hyperlink_format.format(
                link="https://nycstreets.net/Public/Document/ViewPermitPDF/?id=" + i.PermitNumber, text='View PDF')]
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

    return {"data": main_dict_list, "layout": layout_map}


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

app.layout = html.Div([
    # dcc.Tabs(id='tabs-example', value='tab-1', children=[
    #     dcc.Tab(label='Tab one', value='tab-1', children=[html.Div(
            html.Div([
                html.Div(
                    [
                        html.H1(children='New York City Noise Complaints',
                                className='nine columns'),

                        html.Div(children='''

                        ''',
                                 className='nine columns'
                                 ),
                    ], className="row"
                ),
            html.Label(['Created by Siddhanth Shetty for the ', html.A('Sounds Of New York City (SONYC)', href='https://wp.nyu.edu/sonyc/', target='_blank'),' project with support from Charlie Mydlarz and Graham Dove']),
            html.Div([html.P('The following dashboard allows you to dive deeper and find trends '
                            'in Noise complaints over the last two months. You also have the ability to '
                            'view street construction permits issued in the last two months. '
                            'The info buttons next to each plot will provide further details on'
                            ' how it can be filtered or interacted with.'),
                      "To get an example of how this tool can be used along with the code to develop it visit the following ",
                      html.A("link.",href="https://github.com/sds695/noise-complaint-dashboard", target='_blank')]),
                html.Div(
                    [
                        html.Div(
                            [
                                html.P('Choose Boroughs:'),
                                dcc.Checklist(
                                    id='boroughs',
                                    options=[
                                        {'label': 'Manhattan', 'value': 'MANHATTAN'},
                                        {'label': 'Bronx', 'value': 'BRONX'},
                                        {'label': 'Queens', 'value': 'QUEENS'},
                                        {'label': 'Brooklyn', 'value': 'BROOKLYN'},
                                        {'label': 'Staten Island', 'value': 'STATEN ISLAND'}
                                    ],
                                    value=['MANHATTAN', 'BRONX', "QUEENS", 'BROOKLYN', 'STATEN ISLAND'],
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
                                    options=[{'label': str(item),
                                              'value': str(item)}
                                             for item in set(map_data['cleaned_descriptor'])],
                                    multi=True,
                                    value=list(set(map_data['cleaned_descriptor']))
                                )
                            ],
                            className='six columns',
                            style={'margin-top': '10','display': 'none'}
                        )
                    ],
                    className='row'
                ),

                html.Div([
                    html.Div(
                        [
                            html.Div(children=[html.H3('Map Graph'),
                                               html.Img(
                                                   id='mapgraph-info',
                                                   src="assets/question-circle-solid.svg",
                                                   n_clicks=0,
                                                   style={'height': '15px', 'width': '15px'}
                                               ),
                                               dbc.Modal(
                                                   [
                                                       dbc.ModalHeader("Header"),
                                                       dbc.ModalBody(children=[
                                                           "The map to can be used to filter the bar chart and heatmap. "
                                                           "Select the points using plotly lasso select and box select. ",
                                                       "To reset selection double click an empty area of the map. ",
                                                           "You can also view the street construction permits by hovering on "
                                                           "the permit and clicking 'View PDF' ",
                                                           "To reset selection double click an empty area of the plot."
                                                       ]
                                                       ),
                                                        Gif.GifPlayer(
                                                                gif='assets/map_filter.gif',
                                                                still='assets/map_filter.png',
                                                            ),
                                                       dbc.ModalFooter(
                                                           dbc.Button(
                                                               "Close", id="close-mapgraph-info", className="ml-auto"
                                                           )
                                                       ),
                                                   ],
                                                   id="modal-mapgraph",
                                               ), ], className="row", style={'padding': '0px 20px 20px 20px'}),
                            dcc.Graph(id='map-graph',
                                      animate=False,
                                      style={'margin-top': '20'})
                        ], className="six columns"
                    ),
                    html.Div([
                        html.Div(children=[html.H3('Bar Chart'),
                                   html.Img(
                                       id='bargraph-info',
                                       src="assets/question-circle-solid.svg",
                                       n_clicks=0,
                                       style={'height': '15px', 'width': '15px'}
                                   ),
                                   dbc.Modal(
                                       [
                                           dbc.ModalHeader("Header"),
                                           dbc.ModalBody(children=[
                                                           "Use the bar-chart to filter the 311 noise complaint types in the map and heatmap."
                                                           "There are two ways you can do this:",
                                                           html.Li("Select multiple bars by holding down the shift key and clicking the bar."),
                                                           html.Li("Use the plotly box select to drag and select multiple bars."),
                                                            ]
                                                        ),
                                           Gif.GifPlayer(
                                                                gif='assets/bar_filter.gif',
                                                                still='assets/bar_filter.png',
                                                            ),
                                           dbc.ModalFooter(
                                               dbc.Button(
                                                   "Close", id="close-bargraph-info", className="ml-auto"
                                               )
                                           ),
                                       ],
                                       id="modal-bargraph",
                                   ), ], className="row"),
                        dcc.Loading(id="loading-icon2",
                                          children=[dcc.Graph(id='bar-graph',
                                                              animate=False,
                                                              style={'margin-top': '20'})
                                                    ], type="default")], className="six columns"),
                ], className='row',
                    style={"margin-top": 20}),

                html.Div([dcc.RadioItems(id='radio-button',
                                         options=[
                                             {'label': 'Heatmap normalized by complaint type', 'value': 'NYC'},
                                             {'label': 'Regular Heatmap', 'value': 'MTL'}
                                         ],
                                         value='MTL'
                                         )], className="row"),
                html.Div(children=[html.H3('Heatmap'),
                                   html.Img(
                                       id='heatmap-info',
                                       src="assets/question-circle-solid.svg",
                                       n_clicks=0,
                                       style={'height': '15px', 'width': '15px'}
                                   ),
                                   dbc.Modal(
                                       [
                                           dbc.ModalHeader("Header"),
                                           dbc.ModalBody(
                                               "The heatmap can be viewed regularly or normalized by each complaint type "
                                               "by using the radio buttons. The select feature in the heatmap can be used to filter"
                                               " the dates that are shown in the map and bar chart. To reset click the 'Reset Axis' button"
                                               " in the Plotly tools."
                                           ),
                                            Gif.GifPlayer(
                                                                gif='assets/heatmap_filter.gif',
                                                                still='assets/heatmap_filter.png',
                                                            ),
                                           dbc.ModalFooter(
                                               dbc.Button(
                                                   "Close", id="close-heatmap-info", className="ml-auto"
                                               )
                                           ),
                                       ],
                                       id="modal-heatmap",
                                   ), ], className="row"),
                html.Div([dcc.Loading(id="loading-icon1",
                                      children=[dcc.Graph(id='heatmap')], type="default")]),

                html.Div(
                    dash_table.DataTable(
                        id='datatable',
                        columns=[{"name": i, "id": i} for i in map_data.columns],
                        data=map_data.to_dict('records'),
                        row_selectable='multi',
                        style_table={
                            'maxHeight': '300px',
                            'overflowY': 'auto'
                        }
                    ), style={'display': 'none'}
                ),
            #]), style={'padding': '0px 20px 20px 20px'})]),
        #dcc.Tab(label='Tab two', value='tab-2'),
    #]),
    #html.Div(id='tabs-example-content')
])],style={'padding': '0px 20px 20px 20px'})


@app.callback(
    Output('datatable', 'data'),
    [Input('type', 'value'),
     Input('boroughs', 'value')])
def update_selected_row_indices(type, borough):
    map_aux = map_data.copy()
    map_aux = map_aux[map_aux["cleaned_descriptor"].isin(type)]
    map_aux = map_aux[map_aux["borough"].isin(borough)]
    rows = map_aux.to_dict('records')
    return rows


@app.callback(
    Output('map-graph', 'figure'),
    [Input('datatable', 'data'),
     Input('datatable', 'selected_rows'),
     Input('heatmap', 'relayoutData'),
     Input('bar-graph', 'selectedData')])
def map_selection(rows, selected_row_indices, heatmap_filter, type_filter):
    try:
        print('Heatmap selected ' + str(heatmap_filter))
        heatmap_selected_startdate = str(dict(heatmap_filter)['xaxis.range[0]']).split(' ')[0]
        heatmap_selected_enddate = str(dict(heatmap_filter)['xaxis.range[1]']).split(' ')[0]
        print(heatmap_selected_startdate)
        aux = pd.DataFrame(rows)
        if type_filter is not None:
            selected_dates = [(point["y"]) for point in type_filter["points"]]
            aux = aux[aux['cleaned_descriptor'].isin(selected_dates)]
        print()
        if selected_row_indices is None:
            return gen_lines(
                aux, heatmap_selected_startdate, heatmap_selected_enddate)
        elif len(selected_row_indices) == 0:
            return gen_lines(
                aux, heatmap_selected_startdate, heatmap_selected_enddate)
        else:
            temp_df = aux[aux.index.isin(selected_row_indices)]
            return gen_lines(
                temp_df, heatmap_selected_startdate, heatmap_selected_enddate)
    except:
        aux = pd.DataFrame(rows)
        if type_filter is not None:
            selected_dates = [(point["y"]) for point in type_filter["points"]]
            aux = aux[aux['cleaned_descriptor'].isin(selected_dates)]
        if selected_row_indices is None:
            return gen_lines(
                aux)
        elif len(selected_row_indices) == 0:
            return gen_lines(
                aux)
        else:
            temp_df = aux[aux.index.isin(selected_row_indices)]
            return gen_lines(
                temp_df)


@app.callback(
    Output('bar-graph', 'figure'),
    [Input('map-graph', 'selectedData'),
     Input('datatable', 'data'),
     Input('heatmap', 'relayoutData')])
def update_figure(rows, dataframe, heatmap_filter):
    aux = pd.DataFrame(dataframe)
    try:
        heatmap_selected_startdate = str(dict(heatmap_filter)['xaxis.range[0]']).split(' ')[0]
        heatmap_selected_enddate = str(dict(heatmap_filter)['xaxis.range[1]']).split(' ')[0]
        aux = aux[(aux['created_date_wo_time'] >= heatmap_selected_startdate) &
                            (aux['created_date_wo_time'] <= heatmap_selected_enddate)]
    except:
        pass
    if rows is None:
        temp_df = aux
    else:
        selected_row_indices = []
        for i in rows['points']:
            selected_row_indices.append(i['pointIndex'])

        temp_df = aux[aux.index.isin(selected_row_indices)]
    layout = go.Layout(
        clickmode='event+select',
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
        ),
        shapes=[{
    'type': 'rect',
    'xref': 'paper',
    'x0': -0.1,
    'x1': 30000,
    'yref': 'y',
    'y0': 0,
    'y1': 0,
    'opacity': 0
  }]
    )

    print(set(temp_df.groupby('cleaned_descriptor', as_index=False).count()['cleaned_descriptor']))
    print(temp_df.groupby('cleaned_descriptor', as_index=False).count().columns)
    grouped_df = temp_df.groupby('cleaned_descriptor', as_index=False).count()
    grouped_df['descriptor_categories'] = 0
    for index, i in grouped_df.iterrows():
        if i['cleaned_descriptor'] in ['Jack Hammering (NC2)', 'Construction Equipment (NC1)',
                                       'Construction Before/After Hours (NM1)']:
            grouped_df['descriptor_categories'].loc[index] = 1
    data = Data([
        go.Bar(
            x=grouped_df.sort_values(by=['descriptor_categories'], ascending=True)['latitude'],
            y=grouped_df.sort_values(by=['descriptor_categories'], ascending=True)['cleaned_descriptor'],
            # x=temp_df.groupby('cleaned_descriptor', as_index = False).count().sort_values(by=['latitude'],ascending=True)['latitude'],
            # y=temp_df.groupby('cleaned_descriptor', as_index = False).count().sort_values(by=['latitude'],ascending=True)['cleaned_descriptor'],
            orientation='h',
            text=grouped_df.sort_values(by=['descriptor_categories'], ascending=True)['latitude'],
            textposition='auto',
            hoverinfo='none'
        )
    ])

    return go.Figure(data=data, layout=layout)


@app.callback(
    Output('heatmap', 'figure'),
    [Input('map-graph', 'selectedData'),
     Input('datatable', 'data'),
     Input('radio-button', 'value'),
     Input('bar-graph', 'selectedData')])
def update_figure(rows, dataframe, radio_button, type_filter):
    aux = pd.DataFrame(dataframe)

    if rows is None:
        temp_df = aux
    else:
        selected_row_indices = []
        for i in rows['points']:
            selected_row_indices.append(i['pointIndex'])

        temp_df = aux[aux.index.isin(selected_row_indices)]
    if type_filter is not None:
        selected_dates = [(point["y"]) for point in type_filter["points"]]
        temp_df = temp_df[temp_df['cleaned_descriptor'].isin(selected_dates)]

    # def df_to_plotly(df, radio_button):
    #     # Normalizing
    #     temp_df = df.groupby(by=['complaint_code', 'created_date_wo_time']).count().reset_index()
    #     temp_grp = temp_df.groupby('complaint_code')
    #     temp_df['mean'] = temp_grp.transform('mean')['borough']
    #     temp_df['std'] = temp_grp.transform('std')['borough']
    #     temp_df['latitude'] = (temp_df['longitude'] - temp_df['mean']) / temp_df['std']
    #     temp_grp1 = temp_df.groupby('complaint_code')
    #     temp_df['latitude'] = temp_df['latitude'] - temp_grp1.transform('min')['latitude']
    #     print(temp_df.columns)
    #     ref_df = temp_df[['created_date_wo_time', 'complaint_code', 'latitude', 'longitude']]
    #     # Closing block
    #     # ref_df = df.groupby(by=['created_date_wo_time', 'complaint_code']).count().reset_index()[
    #     #     ['created_date_wo_time', 'complaint_code', 'latitude']]
    #     filling_records_df = pd.DataFrame(columns=['created_date_wo_time', 'complaint_code', 'latitude', 'longitude'])
    #     for i in ref_df['created_date_wo_time'].unique():
    #         for j in ref_df['complaint_code'].unique():
    #             filling_records_df = filling_records_df.append(
    #                 {'created_date_wo_time': i, 'complaint_code': j, 'latitude': 0, 'longitude': 0}, ignore_index=True)
    #     filled_df = pd.concat([ref_df, filling_records_df]).groupby(
    #         by=['created_date_wo_time', 'complaint_code']).sum().reset_index()
    #
    #     if radio_button == 'MTL':
    #         return {'z': filled_df['longitude'].tolist(),
    #                 'x': filled_df['created_date_wo_time'].tolist(),
    #                 'y': filled_df['complaint_code'].tolist(),
    #                 'colorscale': 'Blues',
    #                 'text': "Number of complaints: " + filled_df['longitude'].map(str) +
    #                         "<br>" + "Date: " + filled_df['created_date_wo_time'].map(str),
    #                 'hoverinfo': 'text'}
    #     else:
    #         return {'z': filled_df['latitude'].tolist(),
    #                 'x': filled_df['created_date_wo_time'].tolist(),
    #                 'y': filled_df['complaint_code'].tolist(),
    #                 'colorscale': 'Blues',
    #                 'text': "Number of complaints: " + filled_df['longitude'].map(str) +
    #                         "<br>" + "Date: " + filled_df['created_date_wo_time'].map(str),
    #                 'hoverinfo': 'text'}
    #
    # heatmap1 = go.Figure(data=go.Heatmap(df_to_plotly(temp_df, radio_button)),
    #                      layout=go.Layout())
    # return heatmap1

    def df_to_plotly(df, radio_button):
        temp_df = df.groupby(by=['complaint_code', 'created_date_wo_time']).count().reset_index()
        if radio_button == 'MTL':
            ref_df = temp_df[['created_date_wo_time', 'complaint_code', 'latitude', 'longitude']]
            filling_records_df = pd.DataFrame(
                columns=['created_date_wo_time', 'complaint_code', 'latitude', 'longitude'])
            for i in ref_df['created_date_wo_time'].unique():
                for j in ref_df['complaint_code'].unique():
                    filling_records_df = filling_records_df.append(
                        {'created_date_wo_time': i, 'complaint_code': j, 'latitude': 0, 'longitude': 0},
                        ignore_index=True)
            filled_df = pd.concat([ref_df, filling_records_df]).groupby(
                by=['created_date_wo_time', 'complaint_code']).sum().reset_index()
            return {'z': filled_df['longitude'].tolist(),
                    'x': filled_df['created_date_wo_time'].tolist(),
                    'y': filled_df['complaint_code'].tolist(),
                    'colorscale': 'Blues',
                    'text': "Number of complaints: " + filled_df['longitude'].map(str) +
                            "<br>" + "Date: " + filled_df['created_date_wo_time'].map(str),
                    'hoverinfo': 'text'}
        else:
            temp_grp = temp_df.groupby('complaint_code')
            temp_df['mean'] = temp_grp.transform('mean')['borough']
            temp_df['std'] = temp_grp.transform('std')['borough']
            temp_df['latitude'] = (temp_df['longitude'] - temp_df['mean']) / temp_df['std']
            temp_grp1 = temp_df.groupby('complaint_code')
            temp_df['latitude'] = temp_df['latitude'] - temp_grp1.transform('min')['latitude']
            print(temp_df.columns)
            ref_df = temp_df[['created_date_wo_time', 'complaint_code', 'latitude', 'longitude']]
            filling_records_df = pd.DataFrame(
                columns=['created_date_wo_time', 'complaint_code', 'latitude', 'longitude'])
            for i in ref_df['created_date_wo_time'].unique():
                for j in ref_df['complaint_code'].unique():
                    filling_records_df = filling_records_df.append(
                        {'created_date_wo_time': i, 'complaint_code': j, 'latitude': 0, 'longitude': 0},
                        ignore_index=True)
            filled_df = pd.concat([ref_df, filling_records_df]).groupby(
                by=['created_date_wo_time', 'complaint_code']).sum().reset_index()
            return {'z': filled_df['latitude'].tolist(),
                    'x': filled_df['created_date_wo_time'].tolist(),
                    'y': filled_df['complaint_code'].tolist(),
                    'colorscale': 'Blues',
                    'text': "Number of complaints: " + filled_df['longitude'].map(str) +
                            "<br>" + "Date: " + filled_df['created_date_wo_time'].map(str),
                    'hoverinfo': 'text'}
    heatmap1 = go.Figure(data=go.Heatmap(df_to_plotly(temp_df, radio_button)),
                         layout=go.Layout())
    return heatmap1

@app.callback(Output("loading-icon1", "children"))
def input_triggers_spinner1():
    return


@app.callback(Output("loading-icon2", "children"))
def input_triggers_spinner2():
    return


@app.callback(
    Output("modal-heatmap", "is_open"),
    [Input("heatmap-info", "n_clicks"), Input("close-heatmap-info", "n_clicks")],
    [State("modal-heatmap", "is_open")],
)
def toggle_modal1(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-bargraph", "is_open"),
    [Input("bargraph-info", "n_clicks"), Input("close-bargraph-info", "n_clicks")],
    [State("modal-bargraph", "is_open")],
)
def toggle_modal2(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

@app.callback(
    Output("modal-mapgraph", "is_open"),
    [Input("mapgraph-info", "n_clicks"), Input("close-mapgraph-info", "n_clicks")],
    [State("modal-mapgraph", "is_open")],
)
def toggle_modal3(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

if __name__ == '__main__':
    app.run_server(debug=False)