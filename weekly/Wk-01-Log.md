# Week 1 Log — The Hardest Category Boundary

**Chiyu Xu · Applied AI Analyst Intern · Week 1**

The hardest part of this week was deciding where one category ends and another begins. The clearest example came from Fari. In one case, Fari raised a fall alert, but the resident had only bent down to pick something up. When I tried to place this report in the taxonomy, none of the existing categories fit.

I first checked whether it was a hardware problem (H3 Sensors). It was not: the camera was working normally. I then checked whether it was a software problem (S4 App & Interface). Again, no: there was no bug and nothing crashed. It was also not a user complaint (U2), because the user did nothing wrong. I realised that all four groups in the original taxonomy assume that something is broken: a battery, a wheel, a connection, an app. In this case nothing was broken. The robot's AI simply made the wrong judgement.

So I added a new category, S5 AI Detection Error. The rule is: when the sensors and software are both working normally, but the AI reaches a wrong conclusion (a false alarm, a missed event, or a wrong recognition), the report belongs to S5. This also covers cases such as emotion being misread, or a Rover flagging an animal as an intruder.

The difficult boundary is between S5 and H3. For example, Fari might measure a resident's heart rate as 40 BPM while the resident is actually fine. This could mean the sensor is faulty, or it could mean the sensor works and the AI's estimate is wrong. My rule is: if the report says the sensor is faulty or dirty, label it H3; if the sensor is working but the result is wrong, label it S5.

Looking ahead to Week 2, I expect S5 to be one of the most ambiguous categories, both for human labellers and for the model, because real field reports rarely say whether the sensor was working. When I build the gold set, I will pay particular attention to S5 and H3, and check whether my two rounds of labelling agree on these categories. If agreement is low, that will tell me the rule needs to be clearer, not just that individual labels need fixing.
