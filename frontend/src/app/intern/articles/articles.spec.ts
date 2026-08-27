import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InternArticles } from './articles';

describe('InternArticles', () => {
  let component: InternArticles;
  let fixture: ComponentFixture<InternArticles>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [InternArticles],
    }).compileComponents();

    fixture = TestBed.createComponent(InternArticles);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
