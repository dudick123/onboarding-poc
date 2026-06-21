var builder = WebApplication.CreateBuilder(args);

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.MapGet("/", () => new { message = "Hello, World!" })
    .WithName("Hello")
    .WithOpenApi();

app.MapGet("/health", () => new { status = "ok" })
    .WithName("Health")
    .WithOpenApi();

app.Run();

// Exposes the implicit Program class for WebApplicationFactory<Program> in tests.
public partial class Program { }
