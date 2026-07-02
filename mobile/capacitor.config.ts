import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.opsbrief.app',
  appName: 'OpsBrief',
  webDir: 'www',
  server: {
    androidScheme: 'https',
    cleartext: false,
    allowNavigation: ['photon-bounce.com', 'opsbrief.com'],
  },
  android: {
    minSdkVersion: 26,
    buildOptions: {
      keystorePath: 'opsbrief-key.jks',
      keystoreAlias: 'opsbrief',
      keystorePassword: '',      // Set via env var or prompt
      keystoreAliasPassword: '', // Set via env var or prompt
    },
  },
  plugins: {
    SplashScreen: {
      launchAutoHide: true,
      backgroundColor: '#0f172a',
      androidSplashResourceName: 'splash',
      showSpinner: false,
    },
    Keyboard: {
      resize: 'none',
    },
    StatusBar: {
      style: 'Dark',
      backgroundColor: '#0f172a',
    },
  },
};

export default config;
