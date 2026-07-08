document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const closeSidebar = document.getElementById('closeSidebar');
    const overlay = document.getElementById('sidebarOverlay');

    function toggleSidebar() {
        sidebar.classList.toggle('show');
        overlay.classList.toggle('active');
    }

    function closeSidebarFunc() {
        sidebar.classList.remove('show');
        overlay.classList.remove('active');
    }

    if (sidebarToggle) sidebarToggle.addEventListener('click', toggleSidebar);
    if (closeSidebar) closeSidebar.addEventListener('click', closeSidebarFunc);
    if (overlay) overlay.addEventListener('click', closeSidebarFunc);

    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992) {
            closeSidebarFunc();
        }
    });

    document.querySelectorAll('.sidebar .nav-link').forEach(function(link) {
        link.addEventListener('click', function() {
            if (window.innerWidth < 992) {
                closeSidebarFunc();
            }
        });
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.sidebar .nav-link[href]');
    if (!navLinks.length) return;

    let currentFile = window.location.pathname.split('/').pop();
    if (!currentFile) currentFile = 'dashboard.html';

    navLinks.forEach(function(link) {
        const href = link.getAttribute('href');
        if (!href || href === '#') return;

        const linkFile = href.split('/').pop();
        link.classList.toggle('active', linkFile === currentFile);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('productionTrendChart');
    const statTotalBpd = document.getElementById('statTotalBpd');
    const statActiveProjects = document.getElementById('statActiveProjects');

    if (!canvas && !statTotalBpd && !statActiveProjects) return;

    fetch('/api/dashboard-stats')
        .then(function(res) { return res.json(); })
        .then(function(body) {
            if (!body.success) return;

            if (statTotalBpd) statTotalBpd.textContent = body.total_bpd_this_month;
            if (statActiveProjects) statActiveProjects.textContent = body.active_projects;

            if (canvas && typeof Chart !== 'undefined') {
                new Chart(canvas, {
                    type: 'bar',
                    data: {
                        labels: body.trend_labels,
                        datasets: [{
                            label: 'BPD Diverifikasi',
                            data: body.trend_data,
                            backgroundColor: '#0d6efd',
                            borderRadius: 6,
                            maxBarThickness: 28
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: { precision: 0, color: '#94a3b8', font: { size: 11 } },
                                grid: { color: '#f1f5f9' }
                            },
                            x: {
                                grid: { display: false },
                                ticks: { color: '#94a3b8', font: { size: 11 } }
                            }
                        }
                    }
                });
            }

            const pieCanvas = document.getElementById('bjlsDoughnutChart');
            if (pieCanvas && typeof Chart !== 'undefined' && body.bjls_labels && body.bjls_data) {
                new Chart(pieCanvas, {
                    type: 'doughnut',
                    data: {
                        labels: body.bjls_labels,
                        datasets: [{
                            data: body.bjls_data,
                            backgroundColor: [
                                '#0d6efd',
                                '#198754',
                                '#ffc107',
                                '#dc3545',
                                '#fd7e14',
                                '#0dcaf0',
                                '#6f42c1',
                                '#6c757d'
                            ],
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '60%',
                        plugins: {
                            legend: {
                                position: 'right',
                                labels: {
                                    color: '#475569',
                                    font: { size: 11 }
                                }
                            }
                        }
                    }
                });
            }
        })
        .catch(function(err) {
            console.error('Gagal memuat statistik dashboard:', err);
        });
});