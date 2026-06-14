declare global {
  namespace App {
    interface Locals {
      subdomain: string | null;
      customDomain: string | null;
    }
  }
}

export {};
