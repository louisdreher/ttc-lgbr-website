import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminArticleList } from './list';

describe('AdminArticleList', () => {
  let component: AdminArticleList;
  let fixture: ComponentFixture<AdminArticleList>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideRouter([])],
      imports: [AdminArticleList],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticleList);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
