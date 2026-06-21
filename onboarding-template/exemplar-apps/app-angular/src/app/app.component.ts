import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  standalone: true,
  template: `
    <main style="font-family: system-ui, sans-serif; padding: 2rem">
      <h1>Hello, World!</h1>
      <p>Angular 18 standalone starter. Replace this component to build your application.</p>
    </main>
  `,
})
export class AppComponent {
  title = 'hello-world';
}
