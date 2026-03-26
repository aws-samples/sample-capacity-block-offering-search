import React, { useState, useEffect } from 'react';
import { Container, Paper, Typography, Box, Tabs, Tab, Alert } from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import SearchForm from './components/SearchForm';
import TaskHistory from './components/TaskHistory';
import axios from 'axios';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
const API_KEY = import.meta.env.VITE_API_KEY;

function App() {
  const [tabValue, setTabValue] = useState(0);
  const [instanceTypesData, setInstanceTypesData] = useState(null);
  const [configLoading, setConfigLoading] = useState(true);
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
      } finally {
        setConfigLoading(false);
      }
    };
    loadConfig();
  }, []);

  const handleSubmitTask = async (formData) => {
    try {
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
    } catch (err) {
      console.error('Error submitting task:', err);
      alert('提交任务失败: ' + (err.response?.data?.error || err.message));
    }
  };

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Container maxWidth="xl" sx={{ py: 4 }}>
        <Paper elevation={3} sx={{ p: 4, mb: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            EC2 Capacity Block Search (异步版本)
          </Typography>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            提交查询任务，通过邮件接收结果
          </Typography>

          <Box sx={{ borderBottom: 1, borderColor: 'divider', mt: 3 }}>
            <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
              <Tab label="提交任务" />
              <Tab label="任务历史" />
            </Tabs>
          </Box>

          {submitSuccess && tabValue === 1 && (
            <Alert severity="success" sx={{ mt: 2 }} onClose={() => setSubmitSuccess(null)}>
              任务已提交！Task ID: {submitSuccess.task_id}
            </Alert>
          )}

          {tabValue === 0 && (
            <Box sx={{ mt: 3 }}>
              {configLoading ? (
                <Typography>加载配置中...</Typography>
              ) : (
                <SearchForm 
                  onSubmit={handleSubmitTask} 
                  instanceTypesData={instanceTypesData} 
                />
              )}
            </Box>
          )}

          {tabValue === 1 && (
            <Box sx={{ mt: 3 }}>
              <TaskHistory />
            </Box>
          )}
        </Paper>
      </Container>
    </LocalizationProvider>
  );
}

export default App;
