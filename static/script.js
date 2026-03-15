document.addEventListener("DOMContentLoaded", function () {

  // ===== СЕКЦІЇ =====
  const sections = document.querySelectorAll("section");

  const sectionObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
      }
    });
  }, { threshold: 0.1, rootMargin: "0px 0px -20px 0px" });

  sections.forEach(section => {
    sectionObserver.observe(section);
  });

  // ===== HERO ФОТО — тільки плавна поява, без підняття =====
  const heroImages = document.querySelectorAll(".hero-images img");

  heroImages.forEach((img, i) => {
    img.style.opacity = "0";
    img.style.transition = `opacity 0.9s cubic-bezier(.16,1,.3,1)`;
    img.style.transitionDelay = `${i * 0.15}s`;
  });

  const heroObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = "1";
        heroObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  heroImages.forEach(img => heroObserver.observe(img));

  // ===== ІНШІ ФОТО — поява + підняття =====
  const images = document.querySelectorAll(
    ".product-card img, .shop-grid img, .florist-card img"
  );

  images.forEach((img, i) => {
    img.style.opacity = "0";
    img.style.transform = "translateY(14px)";
    img.style.transition = "opacity 0.7s cubic-bezier(.16,1,.3,1), transform 0.7s cubic-bezier(.16,1,.3,1)";
    img.style.transitionDelay = `${(i % 4) * 0.1}s`;
  });

  const imageObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = "1";
        entry.target.style.transform = "translateY(0)";
        imageObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -10px 0px" });

  images.forEach(img => imageObserver.observe(img));

  // ===== ФОТО ПРЕВ'Ю У ФОРМІ =====
  const photoInput = document.getElementById("photoInput");
  const preview = document.getElementById("photoPreview");

  if (photoInput) {
    photoInput.addEventListener("change", function () {
      const file = this.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = function (e) {
          preview.src = e.target.result;
          preview.style.display = "block";
        };
        reader.readAsDataURL(file);
      }
    });
  }

});