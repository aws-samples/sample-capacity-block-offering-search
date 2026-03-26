import React, { useState, useEffect } from 'react';
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip, Button, IconButton, CircularProgress, Typography, Alert } from '@mui/material';
import { Refresh, Download } from '@mui/icons-material';
import axios from 'axios';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
const API_KEY = import.meta.env.VITE_API_KEY;

const STATUS_COLORS = {
  PENDING: 'default',
  RUNNING: 'info',
  COMPLETED: 'success',
  FAILED: 'error'
};

function TaskHistory() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState({});

  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_ENDPOINT}/tasks`, {
        headers: { 'X-Api-Key': API_KEY }
      });
      setTasks(response.data.tasks || []);
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTasks();
    const interval = setInterval(loadTasks, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleDownload = async (taskId) => {
    setDownloading(prev => ({ ...prev, [taskId]: true }));
    try {
      const response = await axios.get(`${API_ENDPOINT}/tasks/${taskId}/results`, {
        headers: { 'X-Api-Key': API_KEY }
      });
      
      if (response.data.presigned_url) {
        window.open(response.data.presigned_url, '_blank');
      } else {
        alert('结果文件尚未生成');
      }
    } catch (err) {
      alert('下载失败: ' + (err.response?.data?.error || err.message));
    } finally {
      setDownloading(prev => ({ ...prev, [taskId]: false }));
    }
  };

  if (loading && tasks.length === 0) {
    return <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>;
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  if (tasks.length === 0) {
    return <Typography color="text.secondary" sx={{ p: 2 }}>暂无任务记录</Typography>;
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">任务历史</Typography>
        <IconButton onClick={loadTasks} disabled={loading}>
          <Refresh />
        </IconButton>
      </Box>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>任务 ID</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>实例类型</TableCell>
              <TableCell>持续时间</TableCell>
              <TableCell>开始日期</TableCell>
              <TableCell>子任务</TableCell>
              <TableCell>创建时间</TableCell>
              <TableCell>操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tasks.map((task) => (
              <TableRow key={task.task_id}>
                <TableCell sx={{ 
                  fontFamily: 'monospace', 
                  fontSize: '0.75rem',
                  wordBreak: 'break-all',
                  maxWidth: '150px'
                }}>
                  {task.task_id}
                </TableCell>
                <TableCell>
                  <Chip label={task.status} color={STATUS_COLORS[task.status]} size="small" />
                </TableCell>
                <TableCell>
                  {task.parameters?.instances?.map(inst => inst.type).join(', ') || '-'}
                </TableCell>
                <TableCell>{task.parameters?.duration || '-'} 天</TableCell>
                <TableCell>
                  {task.parameters?.start_date ? new Date(task.parameters.start_date).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '-'}
                </TableCell>
                <TableCell>
                  {task.completed_subtasks || 0} / {task.total_subtasks || 0}
                </TableCell>
                <TableCell>
                  {task.created_at ? new Date(task.created_at).toLocaleString('zh-CN', { 
                    timeZone: 'Asia/Shanghai',
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: false
                  }) : '-'}
                </TableCell>
                <TableCell>
                  {task.status === 'COMPLETED' && (
                    <Button
                      size="small"
                      startIcon={downloading[task.task_id] ? <CircularProgress size={16} /> : <Download />}
                      onClick={() => handleDownload(task.task_id)}
                      disabled={downloading[task.task_id]}
                    >
                      下载
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default TaskHistory;
