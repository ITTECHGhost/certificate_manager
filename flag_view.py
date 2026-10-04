import turtle

# إعداد الشاشة
screen = turtle.Screen()
screen.title("العلم العراقي")
screen.bgcolor("white")

t = turtle.Turtle()
t.speed(0)
t.hideturtle()

# رسم مستطيل
def rectangle(color, x, y, width, height):
    t.penup()
    t.goto(x, y)
    t.pendown()
    t.color(color)
    t.begin_fill()

    for _ in range(2):
        t.forward(width)
        t.right(90)
        t.forward(height)
        t.right(90)
    t.end_fill()

# أبعاد العلم
width = 600
height = 400
x = -300
y = 200

# الأشرطة الثلاثة
rectangle("red", x, y, width, height / 3)
rectangle("white", x, y - height / 3, width, height / 3)
rectangle("black", x, y - 2 * height / 3, width, height / 3)

# كتابة "الله أكبر" باللون الأخضر
t.penup()
t.goto(0, -40)
t.color("green")
t.write("الله أكبر", align="center", font=("Arial", 60, "bold"))

turtle.done()
