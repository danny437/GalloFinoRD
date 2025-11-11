/* Archivo particles.js - fondo animado opcional */
document.addEventListener('DOMContentLoaded', function () {
    if (window.particlesJS) {
        particlesJS('particles-js', {
            particles: {
                number: { value: 50 },
                color: { value: '#00acc1' },
                shape: { type: 'circle' },
                opacity: { value: 0.5 },
                size: { value: 3 },
                line_linked: { enable: true, distance: 150, color: '#00acc1', opacity: 0.4, width: 1 },
                move: { enable: true, speed: 2 }
            },
            interactivity: {
                detect_on: 'canvas',
                events: {
                    onhover: { enable: true, mode: 'repulse' },
                    onclick: { enable: true, mode: 'push' }
                },
                modes: { repulse: { distance: 100 }, push: { particles_nb: 4 } }
            },
            retina_detect: true
        });
    }
});
