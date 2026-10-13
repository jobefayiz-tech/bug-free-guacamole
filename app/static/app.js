// Hide vehicle-only fields unless the rep chose a vehicle. Without JS everything stays visible.
(function () {
  var form = document.querySelector("form[data-vehicle]");
  if (!form) return;
  var vehicleValues = JSON.parse(form.getAttribute("data-vehicle"));
  var select = form.querySelector("select[name=vehicle_type]");
  if (!select) return;
  function apply() {
    var on = vehicleValues.indexOf(select.value) !== -1;
    form.querySelectorAll(".veh").forEach(function (el) {
      el.classList.toggle("hidden", !on);
    });
  }
  select.addEventListener("change", apply);
  apply();
})();

// Confirm dangerous actions (forms with data-confirm)
document.querySelectorAll("form[data-confirm]").forEach(function (f) {
  f.addEventListener("submit", function (e) {
    if (!window.confirm(f.getAttribute("data-confirm"))) e.preventDefault();
  });
});
