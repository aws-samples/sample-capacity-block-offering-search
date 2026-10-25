import { createTheme } from '@mui/material/styles';

// Selectable color schemes. `custom.headerGradient` drives the page header.
export const SCHEMES = [
  {
    key: 'aws',
    label: 'AWS 蓝',
    mode: 'light',
    primary: { main: '#0972D3', dark: '#033160', light: '#539FE5' },
    secondary: { main: '#FF9900', dark: '#EC7211' },
    background: { default: '#F1F3F5', paper: '#FFFFFF' },
    headerGradient: 'linear-gradient(135deg, #033160 0%, #0972D3 100%)',
  },
  {
    key: 'deepblue',
    label: '深蓝',
    mode: 'light',
    primary: { main: '#283593', dark: '#1A237E', light: '#5C6BC0' },
    secondary: { main: '#00ACC1', dark: '#00838F' },
    background: { default: '#EEF0F7', paper: '#FFFFFF' },
    headerGradient: 'linear-gradient(135deg, #1A237E 0%, #3949AB 100%)',
  },
  {
    key: 'green',
    label: '墨绿',
    mode: 'light',
    primary: { main: '#2E7D32', dark: '#1B5E20', light: '#60AD5E' },
    secondary: { main: '#00897B', dark: '#00695C' },
    background: { default: '#EEF3EE', paper: '#FFFFFF' },
    headerGradient: 'linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%)',
  },
  {
    key: 'night',
    label: '夜间',
    mode: 'dark',
    primary: { main: '#539FE5', dark: '#0972D3', light: '#7FBCEC' },
    secondary: { main: '#FFB74D', dark: '#FB8C00' },
    background: { default: '#0E1116', paper: '#161B22' },
    headerGradient: 'linear-gradient(135deg, #0B1E33 0%, #0972D3 100%)',
  },
];

const DEFAULT_SCHEME = 'aws';

export function getScheme(key) {
  return SCHEMES.find(s => s.key === key) || SCHEMES.find(s => s.key === DEFAULT_SCHEME);
}

export function createAppTheme(key) {
  const s = getScheme(key);
  const dark = s.mode === 'dark';
  return createTheme({
    palette: {
      mode: s.mode,
      primary: s.primary,
      secondary: s.secondary,
      background: s.background,
      success: { main: dark ? '#4CAF50' : '#037F51' },
      info: { main: s.primary.main },
      ...(dark ? {} : { text: { primary: '#16191F', secondary: '#5F6B7A' } }),
    },
    shape: { borderRadius: 10 },
    typography: {
      fontFamily: '"Inter", "Segoe UI", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", Arial, sans-serif',
      h4: { fontWeight: 700, letterSpacing: '-0.01em' },
      h6: { fontWeight: 700 },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiButton: { defaultProps: { disableElevation: true } },
      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              fontWeight: 700,
              color: dark ? '#9DA7B3' : '#5F6B7A',
              backgroundColor: dark ? '#1C2430' : '#F8F9FA',
            },
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: { '&:hover': { backgroundColor: dark ? 'rgba(83,159,229,0.08)' : 'rgba(9,114,211,0.04)' } },
        },
      },
      MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
    },
    custom: { headerGradient: s.headerGradient },
  });
}

export default createAppTheme(DEFAULT_SCHEME);
