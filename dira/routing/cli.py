import click
from fastapi.routing import APIRoute

class RouteStyle():
    def __init__(self, route: APIRoute) -> None:
        self.route = route

    def __str__(self) -> str:
        return self.method() + self.url() + self.name()
    
    def to_list(self) -> list:
        return [
            self.method(),
            self.url(),
            self.name(),
        ]

    def method(self) -> str:
        return click.style('|'.join(self.route.methods), fg='green')

    def url(self) -> str:
        return click.style(self.route.path)
    
    def name(self) -> str:
        return click.style(self.route.name, fg='cyan')