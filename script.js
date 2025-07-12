const shutdownBtn = document.getElementById('shutdownBtn');
const shutdownMsg = document.getElementById('shutdownMessage');
const cmdForm = document.getElementById('cmdForm');
const commandInput = document.getElementById('commandInput');
const output = document.getElementById('output');
const netDisplay = document.getElementById('net');

let cpuChart, memChart, diskChart;

const createChart = (ctx, label, color) => {
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label,
        borderColor: color,
        backgroundColor: color + '33',
        data: [],
        fill: true,
        tension: 0.4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 500,
      },
      scales: {
        y: { 
          min: 0, 
          max: 100, 
          title: { display: true, text: '%' },
        },
        x: { 
          title: { display: true, text: 'Time' },
        },
      },
      plugins: {
        legend: { position: 'top' },
      },
    },
  });
};

const updateChart = (chart, value, loadingId, errorId) => {
  if (typeof value !== 'number' || isNaN(value)) {
    console.warn(`Invalid value for ${chart.data.datasets[0].label}:`, value);
    return;
  }
  document.getElementById(loadingId).style.display = 'none';
  document.getElementById(errorId).style.display = 'none';
  chart.data.datasets[0].data.push(value);
  chart.data.labels.push(new Date().toLocaleTimeString());
  if (chart.data.datasets[0].data.length > 10) {
    chart.data.datasets[0].data.shift();
    chart.data.labels.shift();
  }
  chart.update();
};

const showChartError = (loadingId, errorId, message) => {
  document.getElementById(loadingId).style.display = 'none';
  document.getElementById(errorId).style.display = 'block';
  document.getElementById(errorId).textContent = message;
};

const fetchStats = async () => {
  try {
    const res = await fetch('/stats', { timeout: 5000 });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    console.log('Stats received:', data);

    updateChart(cpuChart, data.cpu, 'cpuLoading', 'cpuError');
    updateChart(memChart, data.memory, 'memLoading', 'memError');
    updateChart(diskChart, data.disk, 'diskLoading', 'diskError');
    netDisplay.textContent = `Net Sent: ${data.net_sent}MB | Recv: ${data.net_recv}MB`;
  } catch (err) {
    console.error('Stats fetch failed:', err);
    netDisplay.textContent = `Error fetching stats: ${err.message}`;
    showChartError('cpuLoading', 'cpuError', `Error: ${err.message}`);
    showChartError('memLoading', 'memError', `Error: ${err.message}`);
    showChartError('diskLoading', 'diskError', `Error: ${err.message}`);
  }
};

const appendOutput = (text) => {
  output.textContent += text + '\n';
  output.scrollTop = output.scrollHeight;
};

document.addEventListener('DOMContentLoaded', () => {
  cpuChart = createChart(document.getElementById('cpuChart').getContext('2d'), 'CPU Usage', '#ff4d4f');
  memChart = createChart(document.getElementById('memChart').getContext('2d'), 'Memory Usage', '#fa8c16');
  diskChart = createChart(document.getElementById('diskChart').getContext('2d'), 'Disk Usage', '#1890ff');

  fetchStats();
  setInterval(fetchStats, 5000);

  shutdownBtn.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to shut down the server?')) return;

    shutdownMsg.textContent = 'Initiating shutdown...';
    try {
      const res = await fetch('/shutdown', { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) {
        const data = await res.json();
        if (res.status === 403) throw new Error('Authentication required');
        if (res.status === 501) throw new Error(data.error || 'Server does not support shutdown');
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      shutdownMsg.textContent = data.message || data.error || 'Shutdown initiated.';
    } catch (err) {
      console.error('Shutdown failed:', err);
      shutdownMsg.textContent = `Shutdown failed: ${err.message}`;
    }
    setTimeout(() => shutdownMsg.textContent = '', 5000);
  });

  cmdForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const command = commandInput.value.trim();
    if (!command) return;

    appendOutput(`$ ${command}`);
    commandInput.value = '';
    commandInput.focus();

    try {
      const res = await fetch('/run-command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();

      if (data.output) appendOutput(data.output);
      if (data.error) appendOutput(`Error: ${data.error}`);
    } catch (err) {
      appendOutput(`Error: ${err.message}`);
    }
  });
});