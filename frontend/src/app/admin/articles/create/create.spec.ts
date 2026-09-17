import { provideRouter } from '@angular/router';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdminArticleCreate } from './create';

describe('AdminArticleCreate', () => {
  let component: AdminArticleCreate;
  let fixture: ComponentFixture<AdminArticleCreate>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideRouter([])],
      imports: [AdminArticleCreate],
    }).compileComponents();

    fixture = TestBed.createComponent(AdminArticleCreate);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
