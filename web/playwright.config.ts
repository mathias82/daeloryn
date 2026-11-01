import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', fullyParallel:false, retries:0,
  use:{baseURL:'http://127.0.0.1:4173',viewport:{width:1600,height:1100},trace:'retain-on-failure',screenshot:'only-on-failure'},
  webServer:{command:'npm run dev -- --port 4173 --strictPort',url:'http://127.0.0.1:4173',reuseExistingServer:false},
});
