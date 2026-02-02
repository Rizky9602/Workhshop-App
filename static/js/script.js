// JavaScript for Sidebar Toggle
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const closeSidebar = document.getElementById('closeSidebar');
    const overlay = document.getElementById('sidebarOverlay');

    // Toggle sidebar function
    function toggleSidebar() {
        sidebar.classList.toggle('show');
            overlay.classList.toggle('active');
    }

    // Close sidebar function
    function closeSidebarFunc() {
        sidebar.classList.remove('show');
        overlay.classList.remove('active');
     }

    // Event Listeners
    sidebarToggle.addEventListener('click', toggleSidebar);
    closeSidebar.addEventListener('click', closeSidebarFunc);
    overlay.addEventListener('click', closeSidebarFunc);

    // Close sidebar on window resize if width >= 992px
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992) {
            closeSidebarFunc();
        }
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const uploadLink = document.getElementById('upload_link');
    const fileInput = document.getElementById('fileInput');

    
    if (uploadLink && fileInput) {
        uploadLink.addEventListener('click', function(e) {
            e.preventDefault(); 
            fileInput.click(); 
        });
    } else {
        console.error('Element upload_link atau fileInput tidak ditemukan');
    }
});

