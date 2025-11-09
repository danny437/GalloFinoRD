// static/particles.js
(function () {
  const canvas = document.getElementById("bg");
  if (!canvas) return;

  // Respetar preferencia de "reducir movimiento"
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    canvas.style.display = 'none';
    return;
  }

  const ctx = canvas.getContext("2d");
  let isPaused = false;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  resizeCanvas();

  function getParticleCount() {
    if (window.innerWidth < 600) return 30;
    if (window.innerWidth < 1024) return 60;
    return 100;
  }

  let particles = [];

  class Particle {
    constructor() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.size = Math.random() * 1.5 + 0.5;
      this.speedX = (Math.random() - 0.5) * 0.5;
      this.speedY = (Math.random() - 0.5) * 0.5;
    }
    update() {
      this.x += this.speedX;
      this.y += this.speedY;
      if (this.x < 0) this.x = canvas.width;
      if (this.x > canvas.width) this.x = 0;
      if (this.y < 0) this.y = canvas.height;
      if (this.y > canvas.height) this.y = 0;
    }
    draw() {
      ctx.fillStyle = "rgba(0, 150, 150, 0.3)"; // Más tenue y accesible
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function init() {
    particles = [];
    const count = getParticleCount();
    for (let i = 0; i < count; i++) {
      particles.push(new Particle());
    }
  }

  function animate() {
    if (!isPaused) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.update();
        p.draw();
      });
    }
    requestAnimationFrame(animate);
  }

  // Eventos
  window.addEventListener("resize", () => {
    resizeCanvas();
    init();
  });

  document.addEventListener("visibilitychange", () => {
    isPaused = document.hidden;
  });

  init();
  animate();
})();
