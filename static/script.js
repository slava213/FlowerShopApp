document.addEventListener("DOMContentLoaded", function () {

  // ===== СЕКЦІЇ =====
  const sections = document.querySelectorAll("section");

  const sectionObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
      }
    });
  }, { threshold: 0.08, rootMargin: "0px 0px -12px 0px" });

  sections.forEach(section => {
    sectionObserver.observe(section);
  });

  // ===== КАРТКИ — поява зі стагером при скролі =====
  const revealSelectors = [
    ".product-card",
    ".service-card-new",
    ".occasion-card",
    ".why-card-new",
    ".catalog-card",
    ".rose-card",
    ".vase-card",
    ".acc-card",
    ".micro-chips",
    ".section-band__inner",
    ".section-inline-hint",
    ".section-foot-note",
    ".stats-preface",
  ].join(", ");

  const revealObserver = new IntersectionObserver(
    entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        revealObserver.unobserve(entry.target);
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -32px 0px" }
  );

  document.querySelectorAll(revealSelectors).forEach((el, i) => {
    el.classList.add("reveal-card");
    const col = 6;
    el.style.setProperty("--reveal-delay", `${(i % col) * 0.065}s`);
    revealObserver.observe(el);
  });

  // ===== ТОВАРИ — легкий 3D-нахил по курсору (тільки desktop) =====
  const allowTilt =
    window.matchMedia("(pointer: fine)").matches &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (allowTilt) {
    const maxDeg = 6;
    document.querySelectorAll(".product-card.premium-card").forEach(card => {
      let raf = 0;
      const apply = (e) => {
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          const r = card.getBoundingClientRect();
          const px = (e.clientX - r.left) / r.width - 0.5;
          const py = (e.clientY - r.top) / r.height - 0.5;
          card.style.setProperty("--card-tilt-y", `${px * maxDeg * 2}deg`);
          card.style.setProperty("--card-tilt-x", `${-py * maxDeg * 2}deg`);
        });
      };
      card.addEventListener("mousemove", apply, { passive: true });
      card.addEventListener("mouseleave", () => {
        if (raf) cancelAnimationFrame(raf);
        card.style.setProperty("--card-tilt-x", "0deg");
        card.style.setProperty("--card-tilt-y", "0deg");
      });
    });
  }

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

  // ===== HERO MODAL NAVIGATION =====
  const heroNavModal = document.getElementById("heroNavModal");
  const heroNavConfirm = document.getElementById("heroNavConfirm");
  const heroNavCancel = document.getElementById("heroNavCancel");
  const heroNavText = document.getElementById("heroNavModalText");
  let heroNextUrl = "";

  const closeHeroNavModal = () => {
    if (!heroNavModal) return;
    heroNavModal.classList.remove("open");
    document.body.classList.remove("nav-open");
  };

  if (heroNavModal && heroNavConfirm && heroNavCancel && heroNavText) {
    document.querySelectorAll(".hero-nav-trigger").forEach((card) => {
      card.addEventListener("click", () => {
        heroNextUrl = card.dataset.targetUrl || "";
        const targetName = card.dataset.targetName || "розділ";
        heroNavText.textContent = `Ви дійсно хочете перейти на сторінку з категорією "${targetName}"?`;
        heroNavModal.classList.add("open");
        document.body.classList.add("nav-open");
      });
    });

    heroNavCancel.addEventListener("click", closeHeroNavModal);
    heroNavModal.addEventListener("click", (e) => {
      if (e.target === heroNavModal) closeHeroNavModal();
    });

    heroNavConfirm.addEventListener("click", () => {
      if (heroNextUrl) window.location.href = heroNextUrl;
      closeHeroNavModal();
    });
  }

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