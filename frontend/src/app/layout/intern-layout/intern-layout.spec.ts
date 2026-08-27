import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InternLayoutComponent } from './intern-layout';

describe('InternLayoutComponent', () => {
  let component: InternLayoutComponent;
  let fixture: ComponentFixture<InternLayoutComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InternLayoutComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(InternLayoutComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
