import React, { useState, useEffect } from 'react';
import { Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip, Button, IconButton, CircularProgress, Typography, Alert, LinearProgress, Tooltip } from '@mui/material';
import { Refresh, Download, CheckCircle, ErrorOutline, Schedule, Autorenew, Inbox } from '@mui/icons-material';
import axios from 'axios';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
const API_KEY = import.meta.env.VITE_API_KEY;

const STATUS_META = {
  PENDING: { color: 'default', icon: <Schedule fontSize="small" /> },
  RUNNING: { color: 'info', icon: <Autorenew fontSize="small" /> },
  COMPLETED: { color: 'success', icon: <CheckCircle fontSize="small" /> },
  FAILED: { color: 'error', icon: <ErrorOutline fontSize="small" /> },
  TIMEOUT: { color: 'warning', icon: <ErrorOutline fontSize="small" /> },
};

const fmt = (v) => v ? new Date(v).toLocaleString('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
}) : '-';

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

  const header = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="h6">任务历史</Typography>
        {tasks.length > 0 && <Chip size="small" label={`共 ${tasks.length} 个`} />}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="caption" color="text.secondary">每 10 秒自动刷新</Typography>
        <Tooltip title="立即刷新">
          <span>
            <IconButton onClick={loadTasks} disabled={loading} size="small">
              {loading ? <CircularProgress size={18} /> : <Refresh />}
            </IconButton>
          </span>
        </Tooltip>
      </Box>
    </Box>
  );

  if (loading && tasks.length === 0) {
    return (
      <Box>
        {header}
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}><CircularProgress /></Box>
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        {header}
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (tasks.length === 0) {
    return (
      <Box>
        {header}
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, py: 8, color: 'text.secondary' }}>
          <Inbox sx={{ fontSize: 48, opacity: 0.4 }} />
          <Typography>暂无任务记录</Typography>
          <Typography variant="caption">在「提交任务」标签页发起一次查询</Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      {header}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell>任务 ID</TableCell>
              <TableCell>状态</TableCell>
              <TableCell>实例类型</TableCell>
              <TableCell>持续时间</TableCell>
              <TableCell>开始日期</TableCell>
              <TableCell sx={{ minWidth: 140 }}>进度</TableCell>
              <TableCell>创建时间</TableCell>
              <TableCell align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {tasks.map((task) => {
              const meta = STATUS_META[task.status] || STATUS_META.PENDING;
              const done = task.completed_subtasks || 0;
              const total = task.total_subtasks || 0;
              const pct = total > 0 ? Math.round((done / total) * 100) : 0;
              return (
                <TableRow key={task.task_id} hover>
                  <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.72rem', wordBreak: 'break-all', maxWidth: 140 }}>
                    {task.task_id}
                  </TableCell>
                  <TableCell>
                    <Chip label={task.status} color={meta.color} size="small" icon={meta.icon} variant={task.status === 'COMPLETED' ? 'filled' : 'outlined'} />
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {task.parameters?.instances?.map(inst => (
                        <Chip key={inst.type} label={inst.type} size="small" variant="outlined" />
                      )) || '-'}
                    </Box>
                  </TableCell>
                  <TableCell>{task.parameters?.duration || '-'} 天</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(task.parameters?.start_date)}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LinearProgress
                        variant="determinate"
                        value={pct}
                        color={task.status === 'FAILED' ? 'error' : task.status === 'COMPLETED' ? 'success' : 'primary'}
                        sx={{ flexGrow: 1, height: 6, borderRadius: 3 }}
                      />
                      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>{done}/{total}</Typography>
                    </Box>
                  </TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{fmt(task.created_at)}</TableCell>
                  <TableCell align="right">
                    {task.status === 'COMPLETED' && (
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={downloading[task.task_id] ? <CircularProgress size={16} /> : <Download />}
                        onClick={() => handleDownload(task.task_id)}
                        disabled={downloading[task.task_id]}
                      >
                        下载
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default TaskHistory;
