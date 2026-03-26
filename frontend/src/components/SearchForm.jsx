import React, { useState, useEffect } from 'react';
import { Grid, FormControl, InputLabel, Select, MenuItem, Button, Box, Chip, Checkbox, FormGroup, FormControlLabel, Typography, Divider } from '@mui/material';
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

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ instanceTypes, duration, startDate, forecastDays, regions });
  };

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
          <Button type="submit" variant="contained" size="large" disabled={regions.length === 0 || instanceTypes.length === 0} fullWidth>
            提交任务
          </Button>
        </Grid>
      </Grid>
    </form>
  );
}

export default SearchForm;
