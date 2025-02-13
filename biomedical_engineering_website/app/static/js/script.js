// script.js

document.addEventListener('DOMContentLoaded', function () {
    // Initialize the FullCalendar
    $('#calendar').fullCalendar({
        events: [
            {% for device in devices %}
            {
                title: '{{ device.name }}',
                start: '{% if device.next_maintenance_date %}{{ device.next_maintenance_date.strftime("%Y-%m-%dT%H:%M:%S") }}{% else %}{{ '1970-01-01T00:00:00' }}{% endif %}',
                description: 'Maintenance Schedule: {{ device.maintenance_schedule }}',
                backgroundColor: '#007bff',
                borderColor: '#007bff',
            },
            {% endfor %}
        ],
        editable: false,
        droppable: false,
        header: {
            left: 'prev,next today',
            center: 'title',
            right: 'month,agendaWeek,agendaDay'
        },
        eventRender: function(event, element) {
            element.attr('title', event.description); // Add a tooltip with event description
        },
        height: 'auto'
    });

    // Device search functionality (if needed)
    const searchInput = document.getElementById('searchInput');
    const searchForm = document.getElementById('searchForm');

    // Check if searchInput and searchForm exist on the page
    if (searchInput && searchForm) {
        // Add an event listener for when the user types in the search field
        searchInput.addEventListener('input', function () {
            // Trigger form submission when user starts typing
            searchForm.submit();
        });
    }
});
