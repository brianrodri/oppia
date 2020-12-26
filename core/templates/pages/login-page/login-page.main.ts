import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';
import { LoginPageModule } from './login-page.module';

import 'core-js/es7/reflect';
import 'zone.js';


platformBrowserDynamic().bootstrapModule(LoginPageModule)
  .catch(err => console.error(err));
