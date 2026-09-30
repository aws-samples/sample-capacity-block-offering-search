import React, { useState, useEffect } from 'react';
import { Grid, FormControl, InputLabel, Select, MenuItem, Button, Box, Chip, Checkbox, FormGroup, FormControlLabel, Typography, Divider, FormHelperText, Alert, CircularProgress } from '@mui/material';
import { Send } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';

const DURATIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 21, 28, 35, 42, 49, 56, 63, 70, 77, 84, 91, 98, 105, 112, 119, 126, 133, 140, 147, 154, 161, 168, 175, 182];

function SearchForm({ onSubmit, instanceTypesData }) {
  const [instanceTypes, setInstanceTypes] = useState([]);
  const [duration, setDuration] = useState(21);
  const [startDate, setStartDate] = useState(dayjs());
  const [forecastDays, setForecastDays] = useState(0);
  const [regions, setRegions] = useState([]);
  const [INSTANCE_TYPES, setInstanceTypesList] = useState([]);
  const [ALL_REGIONS, setAllRegions] = useState([]);
  const [REGION_GROUPS, setRegionGroups] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    if (!instanceTypesData) return;
    
    const instanceTypesList = Object.keys(instanceTypesData);
    setInstanceTypesList(instanceTypesList);
    
    const allRegions = new Set();
    Object.values(instanceTypesData).forEach(instance => {
      Object.keys(instance.regions).forEach(region => allRegions.add(region));
    });
    const sortedRegions = Array.from(allRegions).sort();
    setAllRegions(sortedRegions);
    
    const groups = {};
    sortedRegions.forEach(region => {
      const prefix = region.split('-')[0];
      if (!groups[prefix]) groups[prefix] = [];
      groups[prefix].push(region);
    });
    setRegionGroups(groups);
    
    setInstanceTypes(instanceTypesList.length > 0 ? [instanceTypesList[0]] : []);
    setRegions(sortedRegions);
  }, [instanceTypesData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      await onSubmit({ instanceTypes, duration, startDate, forecastDays, regions });
    } catch (err) {
      setSubmitError(err.response?.data?.error || err.message || '提交任务失败');
    } finally {
      setSubmitting(false);
    }
  };

  const selectedRegionCount = regions.length;
  const estimatedSubtasks = instanceTypes.length * selectedRegionCount * (forecastDays + 1);

  const handleSelectAll = () => setRegions(ALL_REGIONS);
  const handleDeselectAll = () => setRegions([]);
  
  const handleGroupToggle = (groupName) => {
    const groupRegions = REGION_GROUPS[groupName];
    const allSelected = groupRegions.every(r => regions.includes(r));
    if (allSelected) {
      setRegions(regions.filter(r => !groupRegions.includes(r)));
    } else {
      setRegions([...new Set([...regions, ...groupRegions])]);
    }
  };

  if (!instanceTypesData) return null;

  return (
    <form onSubmit={handleSubmit}>
      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Alert severity="info">
            <strong>持续时间</strong> = 预留时长（用多久，决定租期长度）；<strong>预测天数</strong> = 从开始日期起再往后查几天（找哪天有货，不改租期）。
            <br />
            例：开始日期 10/01、持续时间 7 天、预测天数 3 天 → 会分别查询 <em>10/01、10/02、10/03、10/04</em> 这 4 个起始日，每个都找一个 <em>7 天</em>的容量块。
          </Alert>
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>实例类型</InputLabel>
            <Select
              multiple
              value={instanceTypes}
              label="实例类型"
              onChange={(e) => setInstanceTypes(e.target.value)}
              renderValue={(selected) => (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {selected.map((value) => <Chip key={value} label={value} size="small" />)}
                </Box>
              )}
            >
              {INSTANCE_TYPES.map((type) => (
                <MenuItem key={type} value={type}>
                  <Checkbox checked={instanceTypes.indexOf(type) > -1} />
                  {type}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>持续时间</InputLabel>
            <Select value={duration} label="持续时间" onChange={(e) => setDuration(e.target.value)}>
              {DURATIONS.map((d) => <MenuItem key={d} value={d}>{d} 天</MenuItem>)}
            </Select>
            <FormHelperText>
              容量块的<strong>预留时长（租期）</strong>：你要占用这批 GPU/加速卡多少天。结束日期 = 开始日期 + 持续时间。
            </FormHelperText>
          </FormControl>
        </Grid>

        <Grid item xs={12} md={6}>
          <DatePicker
            label="开始日期"
            value={startDate}
            onChange={(newValue) => setStartDate(newValue)}
            minDate={dayjs()}
            slotProps={{ textField: { fullWidth: true } }}
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>预测天数</InputLabel>
            <Select value={forecastDays} label="预测天数" onChange={(e) => setForecastDays(e.target.value)}>
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14].map((days) => (
                <MenuItem key={days} value={days}>
                  {days === 0 ? '仅开始日期' : `${days} 天`}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>
              从开始日期起<strong>逐天顺延查询</strong>的天数：查哪几天有容量，不影响租期。「仅开始日期」只查当天；选 N 则查开始日期起连续 N+1 天各自的可用性。
            </FormHelperText>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <Button variant="outlined" size="small" onClick={handleSelectAll}>全选</Button>
            <Button variant="outlined" size="small" onClick={handleDeselectAll}>全不选</Button>
            <Chip label={`已选: ${regions.length}`} color="primary" />
          </Box>
          <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1, p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>选择区域</Typography>
            <FormGroup>
              {Object.entries(REGION_GROUPS).map(([groupName, groupRegions]) => (
                <Box key={groupName} sx={{ mb: 2 }}>
                  <FormControlLabel
                    control={<Checkbox checked={groupRegions.every(r => regions.includes(r))} onChange={() => handleGroupToggle(groupName)} />}
                    label={<Typography variant="subtitle2" fontWeight="bold">{groupName}</Typography>}
                  />
                  <Box sx={{ ml: 4, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {groupRegions.map((region) => (
                      <FormControlLabel
                        key={region}
                        control={<Checkbox checked={regions.includes(region)} onChange={() => {
                          if (regions.includes(region)) {
                            setRegions(regions.filter(r => r !== region));
                          } else {
                            setRegions([...regions, region]);
                          }
                        }} size="small" />}
                        label={region}
                      />
                    ))}
                  </Box>
                  <Divider sx={{ mt: 1 }} />
                </Box>
              ))}
            </FormGroup>
          </Box>
        </Grid>

        <Grid item xs={12}>
          {submitError && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setSubmitError(null)}>{submitError}</Alert>}
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={regions.length === 0 || instanceTypes.length === 0 || submitting}
            fullWidth
            startIcon={submitting ? <CircularProgress size={18} color="inherit" /> : <Send />}
          >
            {submitting ? '提交中…' : '提交任务'}
          </Button>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
            已选 {instanceTypes.length} 种机型 × {selectedRegionCount} 个区域 × {forecastDays + 1} 个起始日
            ≈ <strong>{estimatedSubtasks}</strong> 个查询子任务
          </Typography>
        </Grid>
      </Grid>
    </form>
  );
}

export default SearchForm;
