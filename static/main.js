document.addEventListener('DOMContentLoaded', function(){
  const ctx = document.getElementById('pieChart');
  let chart = null;

  function loadChart(){
    const kind = document.getElementById('chart-kind').value;
    const month = document.getElementById('chart-month').value;
    const year = document.getElementById('chart-year').value;

    // Update summary title
    const summaryTitle = document.querySelector('.card-title');
    if (summaryTitle) {
      summaryTitle.textContent = `สรุปยอดประจำเดือน ${month}/${year}`;
    }

    // Load chart data
    fetch(`/chart-data?kind=${kind}&month=${month}&year=${year}`)
      .then(r=>r.json()).then(data=>{
        if(chart) chart.destroy();
        chart = new Chart(ctx, {
          type: 'pie',
          data: {
            labels: data.labels,
            datasets: [{ data: data.values, backgroundColor: data.labels.map((_,i)=>`hsl(${(i*50)%360} 70% 50%)`)}]
          }
        });
      });

    // Load monthly stats
    fetch(`/monthly-stats?month=${month}&year=${year}`)
      .then(r=>r.json()).then(stats=>{
        if (stats) {
          // Update summary values
          document.querySelector('[data-summary="income"]').textContent = stats.income.toFixed(2);
          document.querySelector('[data-summary="expense"]').textContent = stats.expense.toFixed(2);
          document.querySelector('[data-summary="balance"]').textContent = stats.balance.toFixed(2);
        }
      });
  }

  const btn = document.getElementById('load-chart');
  if(btn) btn.addEventListener('click', loadChart);
  // initial load
  if(document.getElementById('chart-kind')) loadChart();
});