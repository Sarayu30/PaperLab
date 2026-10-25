import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    title: 'PaperLab — From paper to experiment',
    loadComponent: () => import('./landing/landing').then((m) => m.Landing),
  },
  {
    path: 'projects',
    title: 'Projects · PaperLab',
    loadComponent: () => import('./projects/project-list').then((m) => m.ProjectList),
  },
  {
    path: 'projects/new',
    title: 'New project · PaperLab',
    loadComponent: () => import('./projects/project-form').then((m) => m.ProjectForm),
  },
  {
    path: 'projects/:id/edit',
    title: 'Revise setup · PaperLab',
    loadComponent: () => import('./projects/project-form').then((m) => m.ProjectForm),
  },
  {
    path: 'projects/:id',
    title: 'Project · PaperLab',
    loadComponent: () => import('./projects/project-detail').then((m) => m.ProjectDetail),
  },
  { path: '**', redirectTo: 'projects' },
];
