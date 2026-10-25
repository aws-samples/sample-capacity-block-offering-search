import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Chip,
  Button, IconButton, CircularProgress, Typography, Alert, LinearProgress, Tooltip,
  Select, MenuItem, FormControl, TextField, InputAdornment
} from '@mui/material';
import { Refresh, Download, CheckCircle, ErrorOutline, Schedule, Autorenew, Inbox, Cancel, ContentCopy, Search } from '@mui/icons-material';
import axios from 'axios';

const API_ENDPOINT = import.meta.env.VITE_API_ENDPOINT;
const API_KEY = import.meta.env.VITE_API_KEY;

const STATUS_META = {
  PENDING: { color: 'default', icon: <Schedule fontSize="small" /> },
  RUNNING: { color: 'info', icon: <Autorenew fontSize="small" /> },
  COMPLETED: { color: 'success', icon: <CheckCircle fontSize="small" /> },
  FAILED: { color: 'error', icon: <ErrorOutline fontSize="small" /> },
  TIMEOUT: { color: 'warning', icon: <ErrorOutline fontSize="small" /> },
  CANCELLED: { color: 'default', icon: <Cancel fontSize="small" /> },
};
const STATUSES = ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED'];
const CANCELLABLE = new Set(['PENDING', 'RUNNING']);

const fmt = (v) => v ? new Date(v).toLocaleString('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
}) : '-';

const shortId = (id) => (id && id.length > 14 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id);

function TaskHistory() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState(null);
  const [nextToken, setNextToken] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [downloading, setDownloading] = useState({});
  const [cancelling, setCancelling] = useState({});
  const [copiedId, setCopiedId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [search, setSearch] = useState('');
  const expandedRef = useRef(false);  // paused auto-refresh once user loads more

  const loadFirst = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_ENDPOINT}/tasks`, { headers: { 'X-Api-Key': API_KEY } });
      setTasks(response.data.tasks || []);
      setNextToken(response.data.next_token || null);
      setLastRefreshed(new Date());
      expandedRef.current = false;
    } catch (err) {
      setError(err.response?.data?.error || err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (!nextToken) return;
    setLoadingMore(true);
    expandedRef.current = true;
    try {
      const response = await axios.get(`${API_ENDPOINT}/tasks`, {
        headers: { 'X-Api-Key': API_KEY },
        params: { next_token: nextToken },
      });
      setTasks(prev => [...prev, ...(response.data.tasks || [])]);
      setNextToken(response.data.next_token || null);
      setLastRefreshed(new Date());
    } catch (err) {
      alert('加载更多失败: ' + (err.response?.data?.error || err.message));
    } finally {
      setLoadingMore(false);
    }
  };

  useEffect(() => {
    loadFirst();
    const interval = setInterval(() => {
      // Don't clobber manually-loaded extra pages; resume on manual refresh.
      if (!expandedRef.current) loadFirst();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleDownload = async (taskId) => {
    setDownloading(prev => ({ ...prev, [taskId]: true }));
    try {
      const response = await axios.get(`${API_ENDPOINT}/tasks/${taskId}/results`, { headers: { 'X-Api-Key': API_KEY } });
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

  const handleCancel = async (taskId) => {
    if (!window.confirm('确定取消该任务？已完成的子任务结果会保留，但不会生成 CSV。')) return;
    setCancelling(prev => ({ ...prev, [taskId]: true }));
    try {
      await axios.post(`${API_ENDPOINT}/tasks/${taskId}/cancel`, {}, { headers: { 'X-Api-Key': API_KEY } });
      await loadFirst();
    } catch (err) {
      alert('取消失败: ' + (err.response?.data?.error || err.message));
    } finally {
      setCancelling(prev => ({ ...prev, [taskId]: false }));
    }
  };

  const handleCopy = async (taskId) => {
    try {
      await navigator.clipboard.writeText(taskId);
      setCopiedId(taskId);
      setTimeout(() => setCopiedId(c => (c === taskId ? null : c)), 1500);
    } catch { /* clipboard unavailable */ }
  };

  const visibleTasks = useMemo(() => tasks.filter(t =>
    (!statusFilter || t.status === statusFilter) &&
    (!search || (t.task_id || '').toLowerCase().includes(search.trim().toLowerCase()))
  ), [tasks, statusFilter, search]);

  const header = (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2, flexWrap: 'wrap', gap: 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Typography variant="h6">任务历史</Typography>
        {tasks.length > 0 && <Chip size="small" label={`${visibleTasks.length} / ${tasks.length}`} />}
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          size="small" placeholder="搜索任务 ID" value={search}
          onChange={(e) => setSearch(e.target.value)}
          InputProps={{ startAdornment: <InputAdornment position="start"><Search fontSize="small" /></InputAdornment> }}
          sx={{ width: 190 }}
        />
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <Select value={statusFilter} displayEmpty onChange={(e) => setStatusFilter(e.target.value)}>
            <MenuItem value="">全部状态</MenuItem>
            {STATUSES.map(s => <MenuItem key={s} value={s}>{s}</MenuItem>)}
          </Select>
        </FormControl>
        {lastRefreshed && (
          <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
            更新于 {lastRefreshed.toLocaleTimeString('zh-CN', { hour12: false })}
          </Typography>
        )}
        <Tooltip title="立即刷新">
          <span>
            <IconButton onClick={loadFirst} disabled={loading} size="small">
              {loading ? <CircularProgress size={18} /> : <Refresh />}
            </IconButton>
          </span>
        </Tooltip>
      </Box>
    </Box>
  );

  if (loading && tasks.length === 0) {
    return <Box>{header}<Box sx={{ display: 'flex', justifyContent: 'center', p: 6 }}><CircularProgress /></Box></Box>;
  }
  if (error) {
    return <Box>{header}<Alert severity="error">{error}</Alert></Box>;
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
              <TableCell>预测天数</TableCell>
              <TableCell>开始日期</TableCell>
              <TableCell sx={{ minWidth: 140 }}>进度</TableCell>
              <TableCell>创建时间</TableCell>
              <TableCell align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {visibleTasks.map((task) => {
              const meta = STATUS_META[task.status] || STATUS_META.PENDING;
              const done = task.completed_subtasks || 0;
              const total = task.total_subtasks || 0;
              const pct = total > 0 ? Math.round((done / total) * 100) : 0;
              return (
                <TableRow key={task.task_id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <Tooltip title={task.task_id}>
                        <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                          {shortId(task.task_id)}
                        </Typography>
                      </Tooltip>
                      <Tooltip title={copiedId === task.task_id ? '已复制' : '复制 ID'}>
                        <IconButton size="small" onClick={() => handleCopy(task.task_id)} sx={{ p: 0.25 }}>
                          {copiedId === task.task_id
                            ? <CheckCircle sx={{ fontSize: 15 }} color="success" />
                            : <ContentCopy sx={{ fontSize: 15 }} />}
                        </IconButton>
                      </Tooltip>
                    </Box>
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
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {task.parameters?.forecast_days > 0 ? `${task.parameters.forecast_days} 天` : '仅开始日期'}
                  </TableCell>
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
                        size="small" variant="outlined"
                        startIcon={downloading[task.task_id] ? <CircularProgress size={16} /> : <Download />}
                        onClick={() => handleDownload(task.task_id)}
                        disabled={downloading[task.task_id]}
                      >
                        下载
                      </Button>
                    )}
                    {CANCELLABLE.has(task.status) && (
                      <Button
                        size="small" variant="outlined" color="error"
                        startIcon={cancelling[task.task_id] ? <CircularProgress size={16} /> : <Cancel />}
                        onClick={() => handleCancel(task.task_id)}
                        disabled={cancelling[task.task_id]}
                      >
                        取消
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            {visibleTasks.length === 0 && (
              <TableRow>
                <TableCell colSpan={9} align="center" sx={{ color: 'text.secondary', py: 4 }}>
                  没有匹配的任务（筛选/搜索条件仅作用于已加载的 {tasks.length} 条）
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {nextToken && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
          <Button onClick={loadMore} disabled={loadingMore}
            startIcon={loadingMore ? <CircularProgress size={16} /> : null}>
            {loadingMore ? '加载中…' : '加载更多'}
          </Button>
        </Box>
      )}
    </Box>
  );
}

export default TaskHistory;
