import { createTheme } from '@mui/material/styles';

// AWS-inspired palette: console blue + orange accent on a light neutral canvas.
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: '#0972D3', dark: '#033160', light: '#539FE5' },
    secondary: { main: '#FF9900', dark: '#EC7211' },
    background: { default: '#F1F3F5', paper: '#FFFFFF' },
    success: { main: '#037F51' },
    info: { main: '#0972D3' },
    text: { primary: '#16191F', secondary: '#5F6B7A' },
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
        root: { '& .MuiTableCell-head': { fontWeight: 700, color: '#5F6B7A', backgroundColor: '#F8F9FA' } },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: { '&:hover': { backgroundColor: 'rgba(9,114,211,0.04)' } },
      },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600 } } },
  },
});

export default theme;
