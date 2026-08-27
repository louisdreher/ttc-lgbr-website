import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InternEvents } from './events';

describe('InternEvents', () => {
  let component: InternEvents;
  let fixture: ComponentFixture<InternEvents>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InternEvents],
    }).compileComponents();

    fixture = TestBed.createComponent(InternEvents);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
