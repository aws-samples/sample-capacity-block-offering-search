import React, { useState, useEffect } from 'react';
import { Container, Paper, Typography, Box, Tabs, Tab, Alert, Chip, CircularProgress, ThemeProvider, CssBaseline } from '@mui/material';
import { CloudQueue, Search as SearchIcon, History as HistoryIcon } from '@mui/icons-material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import SearchForm from './components/SearchForm';
import TaskHistory from './components/TaskHistory';
import theme from './theme';
import axios from 'axios';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
const API_KEY = import.meta.env.VITE_API_KEY;

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [instanceTypesData, setInstanceTypesData] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState(null);
  const [submitSuccess, setSubmitSuccess] = useState(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        const response = await axios.get(`${API_ENDPOINT}/config`, {
          headers: { 'X-Api-Key': API_KEY }
        });
        setInstanceTypesData(response.data);
      } catch (err) {
        console.error('Error loading config:', err);
        setConfigError(err.response?.data?.error || err.message || '无法加载机型配置');
      } finally {
        setConfigLoading(false);
      }
    };
    loadConfig();
  }, []);

  const handleSubmitTask = async (formData) => {
    const instances = formData.instanceTypes.map(type => ({
      type: type,
      regions: Object.keys(instanceTypesData[type]?.regions || {})
        .filter(r => formData.regions.includes(r))
    })).filter(inst => inst.regions.length > 0);

    const response = await axios.post(`${API_ENDPOINT}/tasks`, {
      instances,
      duration: formData.duration,
      start_date: formData.startDate.toISOString(),
      forecast_days: formData.forecastDays
    }, {
      headers: { 'X-Api-Key': API_KEY, 'Content-Type': 'application/json' }
    });

    setSubmitSuccess(response.data);
    setTabValue(1);
  };

  const instanceTypeCount = instanceTypesData ? Object.keys(instanceTypesData).length : 0;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
          {/* Header */}
          <Box
            sx={{
              background: 'linear-gradient(135deg, #033160 0%, #0972D3 100%)',
              color: '#fff',
              py: { xs: 3, md: 4 },
            }}
          >
            <Container maxWidth="xl">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box sx={{ bgcolor: 'rgba(255,255,255,0.15)', borderRadius: 2, p: 1.2, display: 'flex' }}>
                  <CloudQueue sx={{ fontSize: 34 }} />
                </Box>
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="h4" component="h1">
                    EC2 Capacity Block Search
                  </Typography>
                  <Typography variant="body2" sx={{ opacity: 0.85, mt: 0.5 }}>
                    异步查询 GPU / Trainium 容量块可用性与价格，任务完成后邮件通知
                  </Typography>
                </Box>
                {instanceTypeCount > 0 && (
                  <Chip
                    label={`${instanceTypeCount} 种机型可查`}
                    sx={{ bgcolor: 'rgba(255,255,255,0.18)', color: '#fff', fontWeight: 600 }}
                  />
                )}
              </Box>
            </Container>
          </Box>

          <Container maxWidth="xl" sx={{ py: 4 }}>
            <Paper elevation={2} sx={{ overflow: 'hidden' }}>
              <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
                <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
                  <Tab icon={<SearchIcon fontSize="small" />} iconPosition="start" label="提交任务" sx={{ minHeight: 56 }} />
                  <Tab icon={<HistoryIcon fontSize="small" />} iconPosition="start" label="任务历史" sx={{ minHeight: 56 }} />
                </Tabs>
              </Box>

              <Box sx={{ p: { xs: 2, md: 3 } }}>
                {submitSuccess && tabValue === 1 && (
                  <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSubmitSuccess(null)}>
                    任务已提交！Task ID: <strong>{submitSuccess.task_id}</strong>
                  </Alert>
                )}

                {tabValue === 0 && (
                  configLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 2, py: 8, color: 'text.secondary' }}>
                      <CircularProgress size={22} />
                      <Typography>加载机型配置中…</Typography>
                    </Box>
                  ) : configError ? (
                    <Alert severity="error" sx={{ my: 2 }}>
                      加载机型配置失败：{configError}
                      <br />请检查 API Endpoint 与 API Key 配置（<code>.env</code>）是否正确。
                    </Alert>
                  ) : (
                    <SearchForm onSubmit={handleSubmitTask} instanceTypesData={instanceTypesData} />
                  )
                )}

                {tabValue === 1 && <TaskHistory />}
              </Box>
            </Paper>
          </Container>
        </Box>
      </LocalizationProvider>
    </ThemeProvider>
  );
}

export default App;
