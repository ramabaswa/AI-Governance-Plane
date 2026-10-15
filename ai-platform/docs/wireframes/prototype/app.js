document.addEventListener('DOMContentLoaded', () => {
  const navItems = document.querySelectorAll('.nav-item[data-screen]');
  const sections = document.querySelectorAll('.view-section');
  const message = document.getElementById('prototypeMessage');

  navItems.forEach((item) => {
    item.addEventListener('click', () => {
      const screenId = item.dataset.screen;
      navItems.forEach((navItem) => navItem.classList.toggle('active', navItem === item));
      sections.forEach((section) => {
        section.classList.toggle('active', section.id === `screen-${screenId}`);
      });
      message.textContent = 'Static wireframe only. Navigation made no service call and changed no data.';
    });
  });

  document.querySelectorAll('[data-action="preview"]').forEach((button) => {
    button.addEventListener('click', () => {
      message.textContent = 'Illustrative only — no API request, Kubernetes write, credential issuance, or gateway operation was performed.';
    });
  });
});
