import { Component } from '@angular/core';

@Component({
  selector: 'app-news',
  imports: [],
  templateUrl: './news.html',
  styleUrl: './news.css',
})
export class News {

  articles = [
    {
      category: 'Jugend',
      title: 'Erfolgreiches Wochenende für unsere Jugend',
      date: '12. August 2026',
      text: 'Test Test Test TestUnsere Nachwuchsmannschaften waren am vergangenen Wochenende erfolgreich im Einsatz und konnten starke Ergebnisse erzielen.',
      imageUrl: 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?ixid=M3w4MjcwNjd8MHwxfHNlYXJjaHwxfHxtb3VudGFpbnxlbnwwfHx8fDE3ODY2MDMxMDB8MA&ixlib=rb-4.1.0&fit=max&q=80'
    },
    {
      category: 'Herren',
      title: 'Vorbereitung auf die neue Saison läuft',
      date: '8. August 2026',
      text: 'Die Herrenmannschaften des TTC befinden sich mitten in der Vorbereitung auf die kommende Spielzeit. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger. Nur mal zum test etwas Länger'
    },
    {
      category: 'Verein',
      title: 'Neue Website des TTC entsteht',
      date: '3. August 2026',
      text: 'Wir arbeiten aktuell an einem neuen digitalen Auftritt für den TTC 1970 Langen-Brombach.'
    },
    {
      category: 'Turniere',
      title: 'Kreismeisterschaften in Langen-Brombach',
      date: '28. Juli 2026',
      text: 'Im September richtet unser Verein die diesjährigen Kreiseinzelmeisterschaften aus.'
    }
  ];


}
