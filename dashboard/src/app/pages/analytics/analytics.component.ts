import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
})
export class AnalyticsComponent {
  embedUrl: SafeResourceUrl;

  constructor(sanitizer: DomSanitizer) {
    this.embedUrl = sanitizer.bypassSecurityTrustResourceUrl(
      'https://lookerstudio.google.com/embed/reporting/9682155a-7158-4ede-9d97-01060c17b066'
    );
  }
}
