
async function loadGraph() {
    const dropdown = document.getElementById("dropdown");
    const selectedValue = dropdown.value;
    console.log("Selected graph value: " + selectedValue);

    try {
        // Pass the selected value as a query parameter
        const response = await fetch(`/stats_data?graph=${selectedValue}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json', 
            }
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`Error fetching graph data: ${response.status} ${response.statusText}`, errorText);
            const graphsDiv = document.getElementById("Graphs");
            graphsDiv.innerHTML = `<p style="color: red;">Could not load graph data: ${errorText || response.statusText}</p>`;
            return;
        }

        const result = await response.json();
        const graphsDiv = document.getElementById("Graphs");
        if (result && result.data && result.layout) { 
            Plotly.newPlot(graphsDiv, result.data, result.layout);
        } else if (Array.isArray(result)) { // Handling the case where result is directly the data array for plotly
             Plotly.newPlot(graphsDiv, result);
        }
         else {
            console.error("Received data is not in the expected format for Plotly:", result);
            graphsDiv.innerHTML = `<p style="color: red;">Received data is not in the expected format for Plotly.</p>`;
        }

    } catch (error) {
        console.error("Error in loadGraph:", error);
        const graphsDiv = document.getElementById("Graphs");
        graphsDiv.innerHTML = `<p style="color: red;">An error occurred while loading the graph.</p>`;
    }
}

// event listener to the dropdown
document.addEventListener('DOMContentLoaded', (event) => {
    const dropdown = document.getElementById("dropdown");
    if (dropdown) {
        // Load the initial graph
        loadGraph();

        // event listener for changes
        dropdown.addEventListener("change", loadGraph);
    } else {
        console.error("Dropdown element not found");
    }
});