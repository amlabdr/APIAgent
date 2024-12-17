import dash
from dash import html, dcc, Input, Output, State, ALL, callback_context
import plotly.graph_objs as go
from measurement_plane.measurement_plane_client.MP_client import MeasurementPlaneClient
import time, json
import random  # Assuming random values for example purposes

class CountRatePlotter:
    def __init__(self, channels):
        self.channels = channels
        self.channel_data = {channel: [] for channel in channels}
        self.timestamps = []
        self.start_time = None
        self.reset()

    def reset(self):
        """Reset the internal data to start fresh and initialize the plot."""
        self.channel_data = {channel: [] for channel in self.channels}
        self.timestamps = []
        self.start_time = None
        return self.generate_empty_figure()

    def generate_empty_figure(self):
        """Generate an empty figure for initialization."""
        figure = go.Figure()
        figure.update_layout(
            title={"text": "Count rates of timetaggers channels", "font": {"size": 24}},
            xaxis={"title": {"text": "Time (seconds)", "font": {"size": 18}}, "tickfont": {"size": 14}},
            yaxis={"title": {"text": "Rate/s", "font": {"size": 18}}, "tickfont": {"size": 14}},
            legend={"font": {"size": 16}}
        )
        return figure

    def update_data(self, result):
        if self.start_time is None:
            self.start_time = time.time()

        timestamp = time.time() - self.start_time
        self.timestamps.append(timestamp)

        for channel in self.channels:
            rate = result.get(channel, random.uniform(1, 10))
            self.channel_data[channel].append(rate)

    def generate_figure(self):
        timestamps_to_plot = self.timestamps[-300:]
        
        figure = go.Figure()

        # Define a color palette for the channels
        colors = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", 
            "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
        ]
        
        # Loop through channels and assign colors based on index
        for idx, (channel, data) in enumerate(self.channel_data.items()):
            data_to_plot = data[-300:]
            color = colors[idx % len(colors)]  # Cycle through colors if more channels than colors
            figure.add_trace(go.Scatter(
                x=timestamps_to_plot, 
                y=data_to_plot, 
                mode="lines", 
                name=f"Channel {channel}", 
                line=dict(color=color)
            ))

        # Update layout to include a legend and labels
        figure.update_layout(
            title={"text": "Count rates of timetaggers channels", "font": {"size": 24}},
            xaxis={"title": {"text": "Time (seconds)", "font": {"size": 18}}, "tickfont": {"size": 14}},
            yaxis={"title": {"text": "Rate/s", "font": {"size": 18}}, "tickfont": {"size": 14}},
            legend={"font": {"size": 16}}
        )
        
        return figure

class CoincidencePlotter:
    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the internal data to start fresh and initialize the plot."""
        self.accumulated_histogram = []  # Empty histogram data
        self.bin_edges = []  # Empty bin edges
        self.empty_figure = self.generate_empty_figure()  # Generate and store a blank figure

    def generate_empty_figure(self):
        """Generate an empty figure for initialization."""
        figure = go.Figure()
        figure.update_layout(
            title={"text": "Coincidence Histogram", "font": {"size": 24}},
            xaxis={"title": {"text": "Time (ps)", "font": {"size": 18}}, "tickfont": {"size": 14}},
            yaxis={"title": {"text": "Counts", "font": {"size": 18}}, "tickfont": {"size": 14}},
            legend={"font": {"size": 16}}
        )
        return figure

    def update_data(self, result):
        # Extract histogram data from result
        histo_vals = result["histo_vals"]
        bin_edges = result["bin_edges"]

        # Initialize bin edges and histogram if not set
        if not self.accumulated_histogram:
            self.accumulated_histogram = histo_vals
            self.bin_edges = bin_edges
        else:
            # Accumulate histogram values
            self.accumulated_histogram = [
                x + y for x, y in zip(self.accumulated_histogram, histo_vals)
            ]

    def generate_figure(self):
        """Generate a figure based on accumulated data."""
        # Check if accumulated data is empty
        if not self.accumulated_histogram or not self.bin_edges:
            return self.empty_figure

        # Create a histogram plot
        figure = go.Figure()

        # Plot the accumulated histogram
        figure.add_trace(go.Bar(
            x=self.bin_edges[:-1],  # Use the left edges of the bins
            y=self.accumulated_histogram,
            name="Coincidences",
            marker=dict(color="#1f77b4")
        ))

        # Update layout for better visualization
        figure.update_layout(
            title={"text": "Coincidence Histogram", "font": {"size": 24}},
            xaxis={"title": {"text": "Time (ps)", "font": {"size": 18}}, "tickfont": {"size": 14}},
            yaxis={"title": {"text": "Counts", "font": {"size": 18}}, "tickfont": {"size": 14}},
            legend={"font": {"size": 16}}
        )

        return figure

class MeasurementPlaneApp:
    def __init__(self, broker_url):
        self.app = dash.Dash(__name__)
        self.mpClient = MeasurementPlaneClient(broker_url)
        

        self.capabilities = {}
        self.current_measurement = None
        self.current_measurement_type = None
        
        self.supported_capabilities = ["measure-count-rate", "measure-coincidences"]
        self.plotter = None
        self.latest_figure_data = None  # Store the latest figure data here

        self.setup_layout()
        self.setup_callbacks()

    def setup_layout(self):
        self.app.layout = html.Div([
            html.H1("Measurement Plane GUI", style={"textAlign": "center", "marginBottom": "20px"}),

            html.Div([  # Flexbox container
                # Left Section (1/3 width)
                html.Div([
                    html.H2("Measurement Configuration", style={"textAlign": "center", "marginBottom": "20px"}),
                    # Fetch Capabilities
                    html.Button("Fetch Capabilities", id="fetch-btn", n_clicks=0, style={"marginBottom": "20px"}),
                    dcc.Dropdown(id="capability-dropdown", placeholder="Select Capability", style={"marginBottom": "20px"}),

                    html.Hr(),

                    # Scheduling Section
                    html.H3("Scheduling", style={"marginBottom": "10px"}),
                    html.Label("Start Date-Time:"),
                    dcc.RadioItems(
                        id="start-date-radio",
                        options=[
                            {"label": "Now", "value": "now"},
                            {"label": "Select Date-Time", "value": "custom"}
                        ],
                        value="now",
                        inline=True,
                        style={"marginBottom": "10px"}
                    ),
                    html.Div([
                        html.Div([
                            dcc.DatePickerSingle(
                                id="custom-start-date-picker",
                                placeholder="Select start date",
                                style={"width": "150px", "marginRight": "10px"}
                            ),
                            # Dropdowns for time selection
                            dcc.Dropdown(
                                id="custom-start-hours",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(24)],
                                placeholder="HH",
                                style={"width": "60px", "display": "inline-block", "marginRight": "5px"}
                            ),
                            dcc.Dropdown(
                                id="custom-start-minutes",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(60)],
                                placeholder="MM",
                                style={"width": "60px", "display": "inline-block", "marginRight": "5px"}
                            ),
                            dcc.Dropdown(
                                id="custom-start-seconds",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(60)],
                                placeholder="SS",
                                style={"width": "60px", "display": "inline-block"}
                            ),
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"})
                    ], style={"display": "none"}, id="custom-date-time-container"),
                    html.Label("End Date-Time (optional):"),
                        html.Div([
                            dcc.DatePickerSingle(
                                id="end-date-picker",
                                placeholder="Select end date",
                                style={"width": "150px", "marginRight": "10px"}
                            ),
                            # Dropdowns for end time selection
                            dcc.Dropdown(
                                id="end-hours",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(24)],
                                placeholder="HH",
                                style={"width": "60px", "display": "inline-block", "marginRight": "5px"}
                            ),
                            dcc.Dropdown(
                                id="end-minutes",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(60)],
                                placeholder="MM",
                                style={"width": "60px", "display": "inline-block", "marginRight": "5px"}
                            ),
                            dcc.Dropdown(
                                id="end-seconds",
                                options=[{"label": f"{i:02d}", "value": f"{i:02d}"} for i in range(60)],
                                placeholder="SS",
                                style={"width": "60px", "display": "inline-block"}
                            ),
                        ], style={"display": "flex", "alignItems": "center", "marginBottom": "10px"}),

                    html.Label("Options:"),
                    dcc.Checklist(
                        id="schedule-options",
                        options=[
                            {"label": "Stream", "value": "stream"},
                            {"label": "Redirect to Storage", "value": "redirect"}
                        ],
                        value=["stream"],
                        inline=True,
                        style={"marginBottom": "20px"}
                    ),

                    html.Hr(),

                    # Parameters Section
                    html.H3("Parameters", style={"marginBottom": "10px"}),
                    html.Div(id="parameter-inputs", style={"marginBottom": "20px"}),

                ], style={"flex": "1", "padding": "20px", "borderRight": "2px solid #ccc"}),  # Left Section Styling

                # Right Section (2/3 width)
                html.Div([
                    
                    # Buttons
                    html.Div([
                        html.H2("Measurement Controll", style={"textAlign": "center", "marginBottom": "20px"}),
                        html.Button("Start Measurement", id="start-measurement-btn", n_clicks=0, style={"marginRight": "10px"}),
                        html.Button("Stop Measurement", id="stop-measurement-btn", n_clicks=0),
                    ], style={"marginBottom": "20px", "textAlign": "center"}),
                    html.Hr(),
                    # Results Graph
                    html.H2("Measurement Results", style={"textAlign": "center", "marginBottom": "20px"}),
                    
                    dcc.Graph(id="measurement-plot"),

                    # Status
                    html.Div(id="status", children="Status: Waiting for action", 
                            style={"textAlign": "center", "fontSize": "16px", "marginTop": "10px"}),

                    # Interval for updates
                    dcc.Interval(id="interval-component", interval=1000, n_intervals=0)
                ], style={"flex": "2", "padding": "20px"})  # Right Section Styling

            ], style={"display": "flex", "flexDirection": "row", "height": "90vh"}),  # Flex Container

        ])

    def generate_schedule_string(self, start_option, custom_start_date, start_hours, start_minutes, start_seconds, 
                             end_date, end_hours, end_minutes, end_seconds, schedule_options):
        """
        Generate the schedule string based on input parameters.

        Args:
            start_option (str): "now" or "custom" start option.
            custom_start_date (str): Date in 'YYYY-MM-DD' format for custom start.
            start_hours (str): Selected hours for custom start time.
            start_minutes (str): Selected minutes for custom start time.
            start_seconds (str): Selected seconds for custom start time.
            end_date (str): Date in 'YYYY-MM-DD' format for end.
            end_hours (str): Selected hours for end time.
            end_minutes (str): Selected minutes for end time.
            end_seconds (str): Selected seconds for end time.
            schedule_options (list): List of selected options like ["stream", "redirect"].

        Returns:
            str: Formatted schedule string.
        """
        # Construct Start Date-Time
        if start_option == "now":
            start_datetime = "now"
        elif start_option == "custom" and custom_start_date:
            start_time = f"{start_hours or '00'}:{start_minutes or '00'}:{start_seconds or '00'}"
            start_datetime = f"{custom_start_date} {start_time}"
        else:
            raise ValueError("Invalid start date-time configuration.")

        # Construct End Date-Time
        if end_date:
            end_time = f"{end_hours or '00'}:{end_minutes or '00'}:{end_seconds or '00'}"
            end_datetime = f"{end_date} {end_time}"
        else:
            end_datetime = ""

        # Combine into schedule string
        schedule_parts = [start_datetime, end_datetime, "|".join(schedule_options)]
        return " | ".join(schedule_parts)

    def generate_inputs(self, schema, parent_key=None, max_pairs=2):
        """
        Recursively generate Dash input components from a JSON schema.

        Args:
            schema (dict): The parameters schema.
            parent_key (str): The parent key for nested fields (used for unique IDs).
            max_pairs (int): Max number of items for arrays (e.g., "channels").

        Returns:
            list: A flat list of Dash components representing the schema inputs.
        """
        inputs = []

        for param, details in schema.get("properties", {}).items():
            input_id = f"{parent_key}.{param}" if parent_key else param
            description = details.get("description", "")

            # Handle "array" types (e.g., channels with pairs of endpoint and channel)
            if details.get("type") == "array" and "items" in details:
                items_schema = details["items"]
                num_items = min(details.get("maxItems", max_pairs), max_pairs)

                for i in range(num_items):
                    inputs.append(html.H4(f"Node {i + 1}"))  # Title for each pair
                    nested_inputs = self.generate_inputs(items_schema, parent_key=f"{input_id}_{i}")
                    # Flatten the list before extending
                    if isinstance(nested_inputs, list):
                        inputs.extend(nested_inputs)
                    else:
                        inputs.append(nested_inputs)
                inputs.append(html.H4(f""))

            # Handle "object" types
            elif details.get("type") == "object":
                inputs.append(html.H4(f"{param.capitalize()}"))  # Title for the object
                nested_inputs = self.generate_inputs(details, parent_key=input_id)
                if isinstance(nested_inputs, list):
                    inputs.extend(nested_inputs)
                else:
                    inputs.append(nested_inputs)

            # Handle primitive types (string, number, integer, boolean)
            else:
                input_type = "text"
                if details.get("type") == "number":
                    input_type = "number"
                elif details.get("type") == "integer":
                    input_type = "number"

                inputs.append(
                    html.Div([
                        html.Label(f"{param}: {description}", style={
                            "flex": "1", 
                            "textAlign": "left", 
                            "whiteSpace": "nowrap"
                        }),

                        dcc.Input(
                            id={"type": "param-input", "index": input_id},
                            type=input_type,
                            placeholder=param,
                            value="",
                            style={"flex": "0", "width": "200px", "marginLeft": "10px" }
                        )
                    ], 
                    style={
                        "display": "flex", 
                        "alignItems": "center", 
                        "marginBottom": "10px"
                    }
                    )
                )

        return inputs  # Return a flat list of components
    
    def reconstruct_parameters(self, param_ids, param_values):
        """
        Reconstruct a nested parameter dictionary from flattened keys like "channels_0.channel".

        Args:
            param_ids (list): List of input IDs containing hierarchical keys.
            param_values (list): Corresponding values for the inputs.

        Returns:
            dict: Nested parameter dictionary.
        """
        parameters = {}

        for value, id_dict in zip(param_values, param_ids):
            param_name = id_dict["index"]  # e.g., "channels_0.channel"
            keys = param_name.split(".")  # Split into hierarchical parts

            current_level = parameters  # Start at the root of the parameters dictionary

            for i, key in enumerate(keys):
                # Handle array-like keys (e.g., "channels_0")
                if "_" in key and key.split("_")[1].isdigit():  # Detect "channels_0"
                    base_key, index = key.split("_")
                    index = int(index)

                    # Ensure the base key exists as a list
                    if base_key not in current_level:
                        current_level[base_key] = []

                    # Ensure the list is long enough to accommodate the index
                    while len(current_level[base_key]) <= index:
                        current_level[base_key].append({})

                    # Move to the specific dictionary within the list
                    current_level = current_level[base_key][index]

                else:
                    # For regular keys
                    if i == len(keys) - 1:  # Last key, assign the value
                        current_level[key] = value
                    else:  # Intermediate key, ensure it's a dictionary
                        if key not in current_level:
                            current_level[key] = {}
                        current_level = current_level[key]

        return parameters

    def setup_callbacks(self):
        @self.app.callback(
            Output("capability-dropdown", "options"),
            Input("fetch-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def fetch_capabilities(n_clicks):
            self.capabilities = self.mpClient.get_capabilities(capability_types=self.supported_capabilities)
            options = [{"label": f"{cap['label']} ({cap['endpoint']})", "value": cap_id} for cap_id, cap in self.capabilities.items()]
            return options

        @self.app.callback(
            Output("parameter-inputs", "children"),
            Input("capability-dropdown", "value"),
            prevent_initial_call=True
        )
        def update_parameters_inputs(selected_capability_id):
            if self.plotter:
                self.plotter.generate_empty_figure()

            if selected_capability_id is None or selected_capability_id not in self.capabilities:
                return []

            selected_capability = self.capabilities[selected_capability_id]
            parameters_schema = selected_capability.get("parameters_schema", {})
            
            # Generate inputs dynamically based on the schema
            inputs = self.generate_inputs(parameters_schema, max_pairs=parameters_schema.get("maxItems", 2))

            return inputs

        @self.app.callback(
            Output("custom-date-time-container", "style"),
            [Input("start-date-radio", "value")]
        )
        def toggle_date_picker(start_option):
            if start_option == "custom":
                # Show the date picker and time input
                return {"display": "block"}
            # Hide the date picker and time input when "Now" is selected
            return {"display": "none"}
        
        @self.app.callback(
            Output("status", "children"),
            Input("start-measurement-btn", "n_clicks"),
            Input("stop-measurement-btn", "n_clicks"),
            State("capability-dropdown", "value"),
            State({"type": "param-input", "index": ALL}, "value"),
            State({"type": "param-input", "index": ALL}, "id"),
            State("start-date-radio", "value"),
            State("custom-start-date-picker", "date"),
            State("custom-start-hours", "value"),
            State("custom-start-minutes", "value"),
            State("custom-start-seconds", "value"),
            State("end-date-picker", "date"),
            State("end-hours", "value"),
            State("end-minutes", "value"),
            State("end-seconds", "value"),
            State("schedule-options", "value"),
            prevent_initial_call=True
        )
        def handle_measurement_actions(
                start_n_clicks, stop_n_clicks, capability_id, param_values, param_ids,
                start_option, custom_start_date, start_hours, start_minutes, start_seconds,
                end_date, end_hours, end_minutes, end_seconds, schedule_options
            ):
            triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

            if triggered_id == "start-measurement-btn":
                if self.current_measurement is not None:
                    return "A measurement is already active. Please stop it before starting a new one."

                if capability_id is None or capability_id not in self.capabilities:
                    return "Please select a valid capability."
                
                # Generate the schedule string using the helper function
                try:
                    schedule = self.generate_schedule_string(
                        start_option, custom_start_date, start_hours, start_minutes, start_seconds,
                        end_date, end_hours, end_minutes, end_seconds, schedule_options
                    )
                except ValueError as e:
                    return str(e)
                
                # Reconstruct parameters dynamically
                parameters = self.reconstruct_parameters(param_ids, param_values)
                print("Reconstructed Parameters:", parameters)
        
                if self.plotter:
                    figure = self.plotter.generate_empty_figure()
                    self.latest_figure_data = {'figure': figure} 

                selected_capability = self.capabilities[capability_id]
                parameters_schema = selected_capability.get("parameters_schema", {})
                

                self.current_measurement = self.mpClient.create_measurement(selected_capability)
                self.current_measurement.configure(
                    schedule=schedule,
                    parameters=parameters,
                    result_callback=self.on_result_callback,
                )
                self.mpClient.send_measurement(self.current_measurement)
                self.current_measurement_type = selected_capability.get("capability") if selected_capability else None
                if self.current_measurement_type == "measure-count-rate":
                    self.plotter = CountRatePlotter(parameters["channels"])
                elif self.current_measurement_type == "measure-coincidences":  
                    self.plotter = CoincidencePlotter()
                else:
                    self.plotter = None

                return "Measurement started. Awaiting results..."

            elif triggered_id == "stop-measurement-btn":
                if self.current_measurement:
                    self.mpClient.interrupt_measurement(self.current_measurement)
                    self.current_measurement = None
                    return "Measurement stopped."

                return "No active measurement to stop."

            return dash.no_update

        @self.app.callback(
            Output("measurement-plot", "figure"),
            Input("interval-component", "n_intervals"),
            prevent_initial_call=True
        )
        def update_measurement_plot(n_intervals):
            # Check if there is new data to push
            if self.latest_figure_data:
                figure = self.latest_figure_data["figure"]
                self.latest_figure_data = None  # Clear the stored data after pushing
                return figure
            return dash.no_update

    def on_result_callback(self, result):
        if self.plotter:
            self.plotter.update_data(result[0])
            figure = self.plotter.generate_figure()
            # Update the latest figure data
            self.latest_figure_data = {'figure': figure} 
    
    def run(self):
        self.app.run_server(debug=True, use_reloader=False)

if __name__ == "__main__":
    BROKER_URL = "amqp://localhost:5672/"
    app = MeasurementPlaneApp(BROKER_URL)
    app.run()
