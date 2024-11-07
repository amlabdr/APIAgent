import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import time
from threading import Thread
import random

class DashPlotting:
    def __init__(self, channels):
        self.channels = channels
        self.channel_data = {channel: [] for channel in channels}
        self.timestamps = []

        # Initialize Dash app
        self.app = dash.Dash(__name__)

        # Define the layout
        self.app.layout = html.Div([
            dcc.Graph(id='live-graph'),
            dcc.Interval(
                id='graph-update',
                interval=1000,  # Update every second
                n_intervals=0
            )
        ])

        # Set up the callback to update the graph
        @self.app.callback(
            Output('live-graph', 'figure'),
            [Input('graph-update', 'n_intervals')]
        )
        def update_graph_live(n):
            fig = go.Figure()

            # Update the traces for each channel
            for channel in self.channels:
                fig.add_trace(go.Scatter(x=self.timestamps, y=self.channel_data[channel], mode='lines', name=f'Channel {channel}'))

            fig.update_layout(
                title="Real-Time Plotting",
                xaxis_title="Time",
                yaxis_title="Rate"
            )

            return fig

    def start_server(self):
        # Start the Dash app server
        self.app.run_server(debug=True, use_reloader=False)  # Turn off reloader to avoid double execution

    def on_result_callback(self, result):
        print(f"New Result Received: {result}")
        
        if result:
            result = result[0]  # Assuming result is a list of dicts

            # Append new rates for each channel
            for channel in self.channels:
                self.channel_data[channel].append(result.get(channel, random.uniform(1, 10)))  # Append random value for example
            
            # Append the current timestamp
            self.timestamps.append(time.time())

# Example of usage
channels = ['1', '2', '3']
plotter = DashPlotting(channels)

# Start the Dash server in the main thread
plotter.start_server()

# Simulate result callback with dummy data
def simulate_data():
    for _ in range(20):  # Simulate 20 result callbacks
        result = [{'1': random.uniform(1, 10), '2': random.uniform(1, 10), '3': random.uniform(1, 10)}]
        plotter.on_result_callback(result)
        time.sleep(1)

# Run data simulation in a separate thread
data_thread = Thread(target=simulate_data)
data_thread.start()


