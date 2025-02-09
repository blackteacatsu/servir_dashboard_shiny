from shiny import ui, render, App, reactive
from shinywidgets import output_widget, render_plotly, register_widget
import xarray as xr
import plotly.express as px
import plotly.graph_objects as go

import shared

from modules import calculation, interface, mapping


# --- Setup page ui ---#
app_ui = ui.page_fillable(
    ui.head_content(ui.include_css(shared.css_file_path),  # include external css style
                    print(shared.css_file_path),
                    ui.tags.link(rel = "icon", type="image/x-icon", href="https://raw.githubusercontent.com/blackteacatsu/dokkuments/refs/heads/main/static/img/university_shield_blue.ico")
                    ),
    ui.card(
        {"style": "background-color: #ffffff; height: 72px"},
        ui.layout_columns(
            ui.tags.img(src ="https://raw.githubusercontent.com/blackteacatsu/servir_dashboard_shiny/refs/heads/main/dump/datavisualization/assets/university_shield_blue_iiL_icon.ico", 
                        height="72px", width="72px"),
            ui.h1(shared.web_app_title), # Make title of the page
            ui.tags.img(src="https://raw.githubusercontent.com/blackteacatsu/servir_dashboard_shiny/main/dump/datavisualization/assets/logoserviramazonia.png", 
                        height="72px", width="auto"),
            ui.tags.img(src = "https://raw.githubusercontent.com/blackteacatsu/servir_dashboard_shiny/main/dump/datavisualization/assets/NASA-Logo-Large.png", 
                        height="72px", width="95px", right="100%", position="absolute")
            )),

    # Add sidebar layout to the page
    ui.layout_sidebar(    
        # Add contents to the side bar
        interface.build_sidebar_content(),

        # Defining the content outside the sidebar
        #ui.output_text_verbatim('selected_pfaf_id'),
        ui.layout_columns(
            ui.card(
                ui.card_header(ui.tags.h2("Map of the Amazon Basin \N{World Map}")),
                output_widget('heatmap')),

            ui.card(
                ui.card_header(ui.tags.h2("Click on polygon to compute zonal average/maximum")),
                output_widget('boxplot'))
                ),
            
        ui.card( {"style": "width: 360px"},
            ui.card_header(ui.tags.h2("Select Time \N{Tear-Off Calendar}")),
            ui.row(ui.output_ui('time_index_slider'),
                   ui.output_text_verbatim("time_index")),
                fill=False,)
        ),
    title="Amazon HydroViewer",
)


def server(input, output, session):
    @reactive.calc
    def redirect_nc_file():
        if input.var_selector() == 'Streamflow_tavg':
            return xr.open_dataset(shared.routing_ensemble_members_path)
            #return ds_ensemble_members
        else:
            return xr.open_dataset(shared.surface_ensemble_members_path)
    
    @output
    @render.ui
    def time_index_slider():
        ds_ensemble_members = redirect_nc_file()
        lon, lat, time = mapping.get_standard_coordinates(ds_ensemble_members)
        #print(time[0])
        if time is not None:
            return ui.input_slider(
                "time_slider", 
                "Move the slider below to switch time instance", 
                min=0, 
                max=len(time)-1,
                animate=True, 
                step=1, 
                value=0,
                ticks=True,
                time_format='2024-08-31 00:00:00')
        return ui.div("No dataset loaded or time variable missing.")

    heatmapfig = mapping.buildregion(shared.hydrobasins_lev05_url)
    register_widget('heatmap', heatmapfig)
    polygon = interface.on_polygon_click(heatmapfig.data[0])

    @output
    @render.text
    def time_index():
        ds_ensemble_members = redirect_nc_file()
        lon, lat, time = mapping.get_standard_coordinates(ds_ensemble_members)
        return f"{interface.format_date(time[input.time_slider()].values)}"
    
    @reactive.effect
    def update_heatmap_figure():
        ds_ensemble_members = redirect_nc_file()
        lon, lat, time = mapping.get_standard_coordinates(ds_ensemble_members)

        selected_var = ds_ensemble_members[input.var_selector()].mean(dim="ensemble").fillna("")
        #selected_var = selected_var.mean(dim="ensemble") # Get average value across all 7-ensemble members
        #selected_var = selected_var.fillna('') # Replacing NaN data point
        ds_ensemble_members.close()
        #print(selected_var)

        # Clear the previous heatmap trace (if it exists)
        if len(heatmapfig.data) > 1:
            heatmapfig.data = heatmapfig.data[:1]  # Keep only the first trace (polygon)

        #print(input.time_slider())
        if input.var_selector() == 'SoilMoist_inst':
            heatmapfig.add_trace(
                go.Heatmap(z = selected_var.isel(time = input.time_slider(), 
                                                 SoilMoist_profiles = int(input.profile_selector())), 
                                                 x=lon, 
                                                 y=lat, 
                                                 hoverinfo='skip'
                                                 ))

        elif input.var_selector() == 'SoilTemp_inst':
            heatmapfig.add_trace(
                go.Heatmap(z = selected_var.isel(time = input.time_slider(), 
                                                 SoilTemp_profiles = int(input.profile_selector())), 
                                                 x=lon, 
                                                 y=lat, 
                                                 hoverinfo='skip'
                                                 ))
        else:
            heatmapfig.add_trace(
                go.Heatmap(z = selected_var.isel(time = input.time_slider()), 
                           x=lon, 
                           y=lat,
                           hoverinfo='skip'
                           ))  
    
    # Boxplot 
    @render_plotly
    def boxplot():
        ds_ensemble_members = redirect_nc_file()
        lon, lat, time = mapping.get_standard_coordinates(ds_ensemble_members)

        # Initially display an empty figure
        if polygon() == 'Waiting input': 
            return px.box().update_layout(
                    xaxis=dict(visible=False),
                    yaxis=dict(visible=False),
                    annotations=[dict(
                        text=f"{polygon()}",
                        showarrow=False,
                        font=dict(size=20)
                    )]
                )
        #
        else:
            #print(input.var_selector())
            summary = calculation.get_zonal_average_or_maximum(shared.hydrobasins_lev05_url, 
                                                               ds_ensemble_members, 
                                                               int(polygon()), 
                                                               input.var_selector(), 
                                                               lon, lat)
            ds_ensemble_members.close()

            if input.var_selector() == 'SoilMoist_inst': # handler if user select soil moisture
                summary  = summary[summary["SoilMoist_profiles"] == int(input.profile_selector())]
                #print(summary)

                return px.box(summary, 
                              y=input.var_selector(), 
                              x = 'time', color='time', 
                              title=f'Displaying zonal average in {polygon()} @profile level {input.profile_selector()}')

            elif input.var_selector() == 'SoilTemp_inst': # handler if user select soil temperature
                summary  = summary[summary["SoilTemp_profiles"] == int(input.profile_selector())]
                return px.box(summary, 
                              y=input.var_selector(), 
                              x = 'time', color='time', 
                              title=f'Displaying zonal average in {polygon()} @profile level {input.profile_selector()}')
                
            else:
                return px.box(summary, 
                              y=input.var_selector(), 
                              x = 'time', 
                              color='time', 
                              title=f'Displaying spread of ensemble members average in zone {polygon()}')
        
app=App(app_ui, server)